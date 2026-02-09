# dexcom-osc-bridge

Dexcom Share -> Quest chatbox OSC bridge, matching Home Assistant's Share-style integration pattern.

## Windows quick start (recommended)

If you use `windows_easy_start.bat`, you do not need to run any `pip install` commands manually.

`windows_easy_start.bat` does all of this for you:
- creates `.venv`
- installs dependencies (`cryptography`, `python-osc`, `pydexcom`, `zeroconf`)
- runs first-time Dexcom credential setup
- starts the bridge

Steps:
1. Install Python 3 for Windows from https://www.python.org/downloads/windows/ and enable "Add python.exe to PATH".
2. Open this repo folder.
3. Double-click `windows_easy_start.bat`.
4. Leave Quest IP as `auto` (recommended) for OSCQuery detection, or enter it manually.

## Manual setup (optional)

Use this only if you do not want to use the `.bat` file (or are on Linux/macOS).

Install dependencies:

```bash
python3 -m pip install -r requirements.txt
```

If `pydexcom` is unavailable on your index:

```bash
python3 -m pip install python-osc cryptography zeroconf git+https://github.com/gagebenne/pydexcom
```

Set up encrypted credentials once:

```bash
python3 dexcom_share_to_quest3.py setup --region us
```

Run bridge (auto-detect Quest IP via OSCQuery):

```bash
python3 dexcom_share_to_quest3.py run --quest-ip auto --quest-port 9000
```

Run bridge (manual Quest IP):

```bash
python3 dexcom_share_to_quest3.py run --quest-ip 192.168.98.146 --quest-port 9000
```

## Notes

- Dexcom Share must be enabled and publisher credentials are required.
- Region must match your account endpoint: `us`, `ous`, or `jp`.
- OSCQuery auto-detect requires VRChat running with OSC enabled and both devices on the same LAN.
- Default credential path:
`%APPDATA%\dexcom-osc-bridge\dexcom_credentials.json` on Windows, or `~/.config/dexcom-osc-bridge/dexcom_credentials.json` on Linux/macOS.
