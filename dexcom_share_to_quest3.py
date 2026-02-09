#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import json
import os
import time
import getpass
from pathlib import Path
from typing import Any

def default_cred_path() -> Path:
    cfg_dir = Path.home() / ".config" / "dexcom-osc-bridge"
    cfg_dir.mkdir(parents=True, exist_ok=True)
    return cfg_dir / "dexcom_credentials.json"


def derive_fernet_key(master_passphrase: str, salt: bytes) -> bytes:
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=200_000,
    )
    return base64.urlsafe_b64encode(kdf.derive(master_passphrase.encode("utf-8")))


def encrypt_password(password: str, master_passphrase: str) -> dict[str, str]:
    from cryptography.fernet import Fernet

    salt = os.urandom(16)
    key = derive_fernet_key(master_passphrase, salt)
    token = Fernet(key).encrypt(password.encode("utf-8"))
    return {
        "salt_b64": base64.b64encode(salt).decode("ascii"),
        "pw_token": token.decode("ascii"),
    }


def decrypt_password(blob: dict[str, str], master_passphrase: str) -> str:
    from cryptography.fernet import Fernet

    salt = base64.b64decode(blob["salt_b64"])
    key = derive_fernet_key(master_passphrase, salt)
    pw = Fernet(key).decrypt(blob["pw_token"].encode("ascii"))
    return pw.decode("utf-8")


def save_credentials(path: Path, region: str, username: str, encrypted_pw_blob: dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": 1,
        "region": region,
        "username": username,
        "encrypted_password": encrypted_pw_blob,
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.chmod(path, 0o600)


def load_credentials(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def trend_arrow(trend: str | None) -> str:
    if not trend:
        return ""
    d = trend.lower().replace("_", "").replace("-", "").replace(" ", "")
    return {
        "doubleup": "↑↑",
        "singleup": "↑",
        "fortyfiveup": "↗",
        "flat": "→",
        "fortyfivedown": "↘",
        "singledown": "↓",
        "doubledown": "↓↓",
    }.get(d, "")


def normalize_region(region: str) -> str:
    r = (region or "").lower().strip()
    if r in ("us", "usa", "unitedstates", "united_states"):
        return "us"
    if r in ("ous", "outside", "outside-us", "outside_of_us", "outsideofus", "eu", "europe", "uk"):
        return "ous"
    if r in ("jp", "japan"):
        return "jp"
    raise SystemExit("Region must be one of: us, ous, jp")


def create_dexcom_client(username: str, password: str, region: str) -> Any:
    from pydexcom import Dexcom

    attempts = [
        {"region": region},
        {"region": region.upper()},
        {"ous": region == "ous", "jp": region == "jp"},
        {"ous": region == "ous"},
    ]
    errors: list[str] = []
    for extra_kwargs in attempts:
        try:
            return Dexcom(username=username, password=password, **extra_kwargs)
        except TypeError as exc:
            errors.append(f"{extra_kwargs}: {exc}")
            continue
    raise RuntimeError(f"Unsupported pydexcom constructor signature. Tried: {' | '.join(errors)}")


def reading_value(reading: Any) -> int:
    if reading is None:
        raise RuntimeError("No glucose reading returned.")
    if isinstance(reading, (int, float)):
        return int(reading)
    if isinstance(reading, str):
        return int(float(reading))
    for attr in ("value", "mg_dl", "mgdl", "glucose"):
        if hasattr(reading, attr):
            return int(getattr(reading, attr))
    raise RuntimeError(f"Unexpected glucose reading type: {type(reading)!r}")


def reading_trend(dex: Any, reading: Any) -> str | None:
    try:
        trend = dex.get_current_trend()
    except AttributeError:
        trend = None
    if trend:
        return trend.name if hasattr(trend, "name") else str(trend)
    for attr in ("trend", "trend_arrow", "trend_description"):
        if hasattr(reading, attr):
            raw = getattr(reading, attr)
            return raw.name if hasattr(raw, "name") else str(raw)
    return None


def cmd_setup(args: argparse.Namespace) -> None:
    cred_path = Path(args.cred_file).expanduser()
    region = normalize_region(args.region)

    username = args.username or input("Dexcom username/email/phone: ").strip()
    if not username:
        raise SystemExit("Username is required.")

    dex_pw = getpass.getpass("Dexcom password (hidden): ").strip()
    if not dex_pw:
        raise SystemExit("Dexcom password is required.")

    master1 = getpass.getpass("Create master passphrase (hidden): ").strip()
    master2 = getpass.getpass("Re-enter master passphrase: ").strip()
    if not master1:
        raise SystemExit("Master passphrase is required.")
    if master1 != master2:
        raise SystemExit("Master passphrases did not match. Aborting.")

    enc_blob = encrypt_password(dex_pw, master1)
    save_credentials(cred_path, region, username, enc_blob)
    print(f"Saved encrypted credentials to: {cred_path}")


def cmd_run(args: argparse.Namespace) -> None:
    from pythonosc.udp_client import SimpleUDPClient

    cred_path = Path(args.cred_file).expanduser()
    if not cred_path.exists():
        raise SystemExit(f"Credential file not found: {cred_path}\nRun: {Path(__file__).name} setup")

    cfg = load_credentials(cred_path)
    region = normalize_region(cfg["region"])
    username = cfg["username"]

    master = getpass.getpass("Master passphrase (hidden): ").strip()
    password = decrypt_password(cfg["encrypted_password"], master)
    dex = create_dexcom_client(username=username, password=password, region=region)

    client = SimpleUDPClient(args.quest_ip, args.quest_port)
    last_bg = None
    print(
        "Running Dexcom(Share)->OSC: "
        f"Quest {args.quest_ip}:{args.quest_port} interval={args.interval}s min_delta={args.min_delta}"
    )

    while True:
        try:
            reading = dex.get_current_glucose_reading()
            bg = reading_value(reading)
            trend = reading_trend(dex, reading)
            arrow = trend_arrow(trend)

            if last_bg is None or abs(bg - last_bg) >= args.min_delta:
                msg = f"BG {bg} {arrow}".strip()
                client.send_message("/chatbox/input", [msg, True])
                print("Sent:", msg)
                last_bg = bg
            else:
                print("No significant change:", bg)
        except Exception as exc:
            print("Error:", exc)

        time.sleep(args.interval)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Dexcom Share (Home Assistant style) -> VRChat Quest chatbox bridge via OSC"
    )
    parser.add_argument(
        "--cred-file",
        default=str(default_cred_path()),
        help="Path to encrypted credential JSON",
    )

    sub = parser.add_subparsers(dest="cmd", required=True)

    s_setup = sub.add_parser("setup", help="Store Dexcom credentials encrypted in a local file")
    s_setup.add_argument("--region", default="us", help="us | ous | jp")
    s_setup.add_argument("--username", default=None)
    s_setup.set_defaults(func=cmd_setup)

    s_run = sub.add_parser("run", help="Run the bridge")
    s_run.add_argument("--quest-ip", default="192.168.98.146")
    s_run.add_argument("--quest-port", type=int, default=9000)
    s_run.add_argument("--interval", type=int, default=30)
    s_run.add_argument("--min-delta", type=int, default=2)
    s_run.set_defaults(func=cmd_run)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
