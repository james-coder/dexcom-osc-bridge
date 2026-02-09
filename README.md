# dexcom-osc-bridge

Dexcom Share -> Quest chatbox OSC bridge, matching Home Assistant's Share-style integration pattern.

## Windows quick start (recommended)

If you use `windows_easy_start.bat`, you do not need to run any `pip install` commands manually.

### Download from GitHub (ZIP)

1. Download: https://github.com/james-coder/dexcom-osc-bridge/archive/refs/heads/master.zip
2. Right-click the downloaded ZIP and choose "Extract All...".
3. Open the extracted folder (usually `dexcom-osc-bridge-master`).

### Run

`windows_easy_start.bat` does all of this for you:
- auto-updates from GitHub if `git` is installed and this folder is a git clone
- prints the current build hash at startup
- creates `.venv`
- installs dependencies (`cryptography`, `python-osc`, `pydexcom`, `zeroconf`)
- runs first-time Dexcom credential setup (with login verification)
- starts the bridge

Steps:
1. Install Python 3 for Windows from https://www.python.org/downloads/windows/ and enable "Add python.exe to PATH".
2. Open the extracted repo folder.
3. On your Quest, open VRChat settings and enable OSC.
4. Double-click `windows_easy_start.bat`.
5. During first-time setup, enter Dexcom password once (or choose visible password entry).
6. On later runs, you can choose to re-enter Dexcom credentials when prompted.
7. Leave Quest IP as `auto` (recommended) for OSCQuery detection, or enter it manually.
8. If messages do not show up in VRChat, turn on VRChat OSC debugging and confirm `/chatbox/input` is being received.

Auto-update note:
- If you downloaded a ZIP, there is no `.git` folder, so auto-update is skipped.
- For automatic pull updates, clone with git instead of ZIP.

### Git for auto-update (optional)

Use this only if you want `windows_easy_start.bat` to auto-pull updates.

1. Install Git for Windows: https://git-scm.com/download/win
2. Open a new `cmd.exe` window and run:

```bat
git --version
where git
```

If both commands work, Git is available on PATH.

To use auto-update, clone the repo instead of using ZIP:

```bat
git clone https://github.com/james-coder/dexcom-osc-bridge.git
cd dexcom-osc-bridge
windows_easy_start.bat
```

You can also print the running build hash manually:

```bat
.venv\Scripts\python.exe dexcom_share_to_quest3.py --version
```

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

If you want password input to be visible while typing:

```bash
python3 dexcom_share_to_quest3.py setup --region us --visible-password
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
- For Quest troubleshooting, use VRChat OSC debugging to verify OSC traffic while the bridge is running.
- Setup now verifies Dexcom Share login before saving credentials, so auth issues are caught early.
- Default credential path:
`%APPDATA%\dexcom-osc-bridge\dexcom_credentials.json` on Windows, or `~/.config/dexcom-osc-bridge/dexcom_credentials.json` on Linux/macOS.
