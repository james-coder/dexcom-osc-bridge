# dexcom-osc-bridge

Dexcom Share -> Quest chatbox OSC bridge, matching Home Assistant's Share-style integration pattern.

## Install

```bash
pip install python-osc cryptography pydexcom
```

If `pydexcom` is unavailable on your index, install from GitHub:

```bash
pip install git+https://github.com/gagebenne/pydexcom
```

## Usage

Set up encrypted credentials once:

```bash
python3 dexcom_share_to_quest3.py setup --region us
```

Run bridge:

```bash
python3 dexcom_share_to_quest3.py run --quest-ip 192.168.98.146 --quest-port 9000
```

## Notes

- Dexcom Share must be enabled and publisher credentials are required.
- Region must match your account endpoint: `us`, `ous`, or `jp`.
