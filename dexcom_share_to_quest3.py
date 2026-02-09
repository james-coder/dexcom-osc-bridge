#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import json
import os
import time
import getpass
import socket
import threading
from pathlib import Path
from typing import Any


def dependency_error(package_name: str) -> SystemExit:
    return SystemExit(
        f"Missing dependency '{package_name}'. Install with: pip install -r requirements.txt"
    )


OSCQUERY_SERVICE_TYPE = "_oscjson._tcp.local."


def default_cred_path() -> Path:
    if os.name == "nt":
        appdata = os.environ.get("APPDATA")
        base_dir = Path(appdata) if appdata else (Path.home() / "AppData" / "Roaming")
        cfg_dir = base_dir / "dexcom-osc-bridge"
    else:
        cfg_dir = Path.home() / ".config" / "dexcom-osc-bridge"
    cfg_dir.mkdir(parents=True, exist_ok=True)
    return cfg_dir / "dexcom_credentials.json"


def derive_fernet_key(master_passphrase: str, salt: bytes) -> bytes:
    try:
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    except ModuleNotFoundError as exc:
        raise dependency_error("cryptography") from exc

    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=200_000,
    )
    return base64.urlsafe_b64encode(kdf.derive(master_passphrase.encode("utf-8")))


def encrypt_password(password: str, master_passphrase: str) -> dict[str, str]:
    try:
        from cryptography.fernet import Fernet
    except ModuleNotFoundError as exc:
        raise dependency_error("cryptography") from exc

    salt = os.urandom(16)
    key = derive_fernet_key(master_passphrase, salt)
    token = Fernet(key).encrypt(password.encode("utf-8"))
    return {
        "salt_b64": base64.b64encode(salt).decode("ascii"),
        "pw_token": token.decode("ascii"),
    }


def decrypt_password(blob: dict[str, str], master_passphrase: str) -> str:
    try:
        from cryptography.fernet import Fernet
    except ModuleNotFoundError as exc:
        raise dependency_error("cryptography") from exc

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
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def load_credentials(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def arrow(direction: str | None) -> str:
    if not direction:
        return ""
    d = direction.lower().replace("_", "").replace("-", "").replace(" ", "")
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
    try:
        from pydexcom import Dexcom
    except ModuleNotFoundError as exc:
        raise dependency_error("pydexcom") from exc

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


def _first_ipv4_from_service_info(info: Any) -> str | None:
    addresses: list[str] = []
    parsed_addresses = getattr(info, "parsed_addresses", None)
    if callable(parsed_addresses):
        try:
            addresses = list(parsed_addresses())
        except Exception:
            addresses = []
    if not addresses:
        raw_addresses = getattr(info, "addresses", []) or []
        for raw in raw_addresses:
            if isinstance(raw, (bytes, bytearray)) and len(raw) == 4:
                addresses.append(socket.inet_ntoa(raw))
    for ip in addresses:
        if ":" not in ip:
            return ip
    return None


def _query_host_info(ip: str, tcp_port: int, timeout: float = 1.5) -> dict[str, Any]:
    from urllib.request import urlopen

    urls = [
        f"http://{ip}:{tcp_port}?HOST_INFO",
        f"http://{ip}:{tcp_port}/?HOST_INFO",
    ]
    for url in urls:
        try:
            with urlopen(url, timeout=timeout) as response:
                payload = response.read().decode("utf-8", errors="replace")
            data = json.loads(payload)
            if isinstance(data, dict):
                return data
        except Exception:
            continue
    return {}


def detect_vrchat_osc_endpoint(timeout_s: float) -> tuple[str, int] | None:
    try:
        from zeroconf import ServiceBrowser, ServiceListener, Zeroconf
    except ModuleNotFoundError as exc:
        raise dependency_error("zeroconf") from exc

    class Collector(ServiceListener):
        def __init__(self) -> None:
            self._names: set[str] = set()
            self._lock = threading.Lock()

        def add_service(self, zc: Any, service_type: str, name: str) -> None:
            with self._lock:
                self._names.add(name)

        def update_service(self, zc: Any, service_type: str, name: str) -> None:
            with self._lock:
                self._names.add(name)

        def remove_service(self, zc: Any, service_type: str, name: str) -> None:
            pass

        def snapshot(self) -> list[str]:
            with self._lock:
                return sorted(self._names)

    zc = Zeroconf()
    collector = Collector()
    browser = ServiceBrowser(zc, OSCQUERY_SERVICE_TYPE, collector)
    try:
        time.sleep(max(timeout_s, 0.5))
        names = collector.snapshot()
        candidates: list[dict[str, Any]] = []
        for name in names:
            info = zc.get_service_info(OSCQUERY_SERVICE_TYPE, name, timeout=1000)
            if info is None:
                continue
            service_ip = _first_ipv4_from_service_info(info)
            if not service_ip:
                continue
            host_info = _query_host_info(service_ip, int(info.port))
            host_name = str(host_info.get("NAME", ""))
            osc_ip = str(host_info.get("OSC_IP", "")).strip()
            osc_port = host_info.get("OSC_PORT")
            try:
                osc_port_val = int(osc_port) if osc_port is not None else 9000
            except (TypeError, ValueError):
                osc_port_val = 9000

            target_ip = osc_ip or service_ip
            if target_ip.startswith("127.") and not service_ip.startswith("127."):
                target_ip = service_ip

            service_name_l = name.lower()
            host_name_l = host_name.lower()
            score = 0
            if "vrchat" in service_name_l:
                score += 100
            if "vrchat" in host_name_l:
                score += 80
            if not target_ip.startswith("127."):
                score += 40

            candidates.append(
                {
                    "score": score,
                    "target_ip": target_ip,
                    "osc_port": osc_port_val,
                }
            )

        if not candidates:
            return None
        best = max(candidates, key=lambda item: item["score"])
        return str(best["target_ip"]), int(best["osc_port"])
    finally:
        zc.close()


def resolve_quest_endpoint(quest_ip: str, quest_port: int, timeout_s: float) -> tuple[str, int]:
    requested = (quest_ip or "").strip()
    if requested and requested.lower() not in ("auto", "oscquery"):
        return requested, quest_port

    detected = detect_vrchat_osc_endpoint(timeout_s=timeout_s)
    if not detected:
        raise SystemExit(
            "Could not auto-detect VRChat via OSCQuery.\n"
            "Make sure VRChat is running on Quest, OSC is enabled, and both devices are on the same LAN.\n"
            "Then retry with --quest-ip auto or pass --quest-ip manually."
        )

    detected_ip, _detected_port = detected
    return detected_ip, quest_port


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
    try:
        from pythonosc.udp_client import SimpleUDPClient
    except ModuleNotFoundError as exc:
        raise dependency_error("python-osc") from exc

    cred_path = Path(args.cred_file).expanduser()
    if not cred_path.exists():
        raise SystemExit(f"Credential file not found: {cred_path}\nRun: {Path(__file__).name} setup")

    cfg = load_credentials(cred_path)
    region = normalize_region(cfg["region"])
    username = cfg["username"]

    master = getpass.getpass("Master passphrase (hidden): ").strip()
    password = decrypt_password(cfg["encrypted_password"], master)
    dex = create_dexcom_client(username=username, password=password, region=region)

    quest_ip, quest_port = resolve_quest_endpoint(
        quest_ip=args.quest_ip,
        quest_port=args.quest_port,
        timeout_s=args.oscquery_timeout,
    )
    client = SimpleUDPClient(quest_ip, quest_port)
    last_bg = None
    print(
        "Running Dexcom(Share)->OSC: "
        f"Quest {quest_ip}:{quest_port} interval={args.interval}s min_delta={args.min_delta}"
    )

    while True:
        try:
            reading = dex.get_current_glucose_reading()
            bg = reading_value(reading)
            trend = reading_trend(dex, reading)
            dir_arrow = arrow(trend)

            if last_bg is None or abs(bg - last_bg) >= args.min_delta:
                msg = f"BG {bg} {dir_arrow}".strip()
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
    s_setup.add_argument("--cred-file", default=argparse.SUPPRESS, help=argparse.SUPPRESS)
    s_setup.add_argument("--region", default="us", help="us | ous | jp")
    s_setup.add_argument("--username", default=None)
    s_setup.set_defaults(func=cmd_setup)

    s_run = sub.add_parser("run", help="Run the bridge")
    s_run.add_argument("--cred-file", default=argparse.SUPPRESS, help=argparse.SUPPRESS)
    s_run.add_argument(
        "--quest-ip",
        default="auto",
        help="Quest VRChat IP, or 'auto' to discover via OSCQuery",
    )
    s_run.add_argument("--quest-port", type=int, default=9000)
    s_run.add_argument(
        "--oscquery-timeout",
        type=float,
        default=5.0,
        help="Seconds to wait for OSCQuery auto-discovery when --quest-ip=auto",
    )
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
