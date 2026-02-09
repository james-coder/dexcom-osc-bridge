# dexcom-osc-bridge

Dexcom Share -> Quest chatbox OSC bridge, matching Home Assistant's Share-style integration pattern.

## Windows quick start (easiest)

1. Install Python 3 for Windows from https://www.python.org/downloads/windows/ (enable "Add python.exe to PATH" during install).
2. Open this repo folder.
3. Double-click `windows_easy_start.bat`.
4. On first run, it will create `.venv`, install dependencies, ask for region, and run credential setup.
5. Enter your Quest IP/port and it starts the bridge.

## Install

```bash
python3 -m pip install -r requirements.txt
```

If `pydexcom` is unavailable on your index, install from GitHub:

```bash
python3 -m pip install python-osc cryptography git+https://github.com/gagebenne/pydexcom
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
- Default credential path:
`%APPDATA%\dexcom-osc-bridge\dexcom_credentials.json` on Windows, or `~/.config/dexcom-osc-bridge/dexcom_credentials.json` on Linux/macOS.
