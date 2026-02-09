@echo off
setlocal enableextensions
cd /d "%~dp0"

set "GIT_SHA=unknown"

where git >nul 2>nul
if errorlevel 1 goto :no_git
if not exist ".git" goto :not_clone

echo Checking for updates from GitHub...
git pull --ff-only >nul 2>nul
if errorlevel 1 (
  echo Git auto-update failed. Continuing with local files.
) else (
  echo Git auto-update complete.
)
git rev-parse --short HEAD > "%TEMP%\dexcom_bridge_sha.txt" 2>nul
if exist "%TEMP%\dexcom_bridge_sha.txt" set /p GIT_SHA=<"%TEMP%\dexcom_bridge_sha.txt"
del "%TEMP%\dexcom_bridge_sha.txt" >nul 2>nul
goto :after_git

:no_git
echo Git not found. Skipping auto-update.
goto :after_git

:not_clone
echo Git found, but this folder is not a git clone. Skipping auto-update.

:after_git
echo Running dexcom-osc-bridge build %GIT_SHA%
set "DEXCOM_BRIDGE_BUILD=%GIT_SHA%"

if exist ".venv\Scripts\python.exe" goto :have_venv

echo Creating local virtual environment...
where py >nul 2>nul
if errorlevel 1 goto :try_python
py -3 -m venv .venv
if errorlevel 1 goto :fail
goto :have_venv

:try_python
where python >nul 2>nul
if errorlevel 1 (
  echo Python 3 is not installed or not on PATH.
  echo Install from https://www.python.org/downloads/windows/
  pause
  exit /b 1
)
python -m venv .venv
if errorlevel 1 goto :fail

:have_venv
set "VENV_PY=.venv\Scripts\python.exe"

"%VENV_PY%" -c "import cryptography, pythonosc, pydexcom, zeroconf" >nul 2>nul
if not errorlevel 1 goto :deps_ok

echo Installing dependencies...
"%VENV_PY%" -m pip install --upgrade pip
if errorlevel 1 goto :fail

"%VENV_PY%" -m pip install -r requirements.txt
if errorlevel 1 (
  echo Standard install failed. Trying pydexcom GitHub fallback...
  "%VENV_PY%" -m pip install python-osc cryptography zeroconf "git+https://github.com/gagebenne/pydexcom"
  if errorlevel 1 goto :fail
)

:deps_ok
if defined APPDATA (
  set "CRED_FILE=%APPDATA%\dexcom-osc-bridge\dexcom_credentials.json"
) else (
  set "CRED_FILE=%USERPROFILE%\AppData\Roaming\dexcom-osc-bridge\dexcom_credentials.json"
)

set "RUN_SETUP=n"
if exist "%CRED_FILE%" (
  echo.
  set /p RUN_SETUP=Re-enter Dexcom credentials now? [y/N]:
)
if /I "%RUN_SETUP%"=="y" goto :do_setup
if exist "%CRED_FILE%" goto :run_prompt

:do_setup
echo.
if exist "%CRED_FILE%" (
  echo Running credential setup.
) else (
  echo First-time setup: encrypted Dexcom credentials not found.
)
set "REGION=us"
set /p REGION=Enter region [us/ous/jp] (default us):
if "%REGION%"=="" set "REGION=us"
set "VISIBLE_PW=n"
set /p VISIBLE_PW=Show Dexcom password while typing? [y/N]:
set "VISIBLE_PW_FLAG="
if /I "%VISIBLE_PW%"=="y" set "VISIBLE_PW_FLAG=--visible-password"

"%VENV_PY%" dexcom_share_to_quest3.py --cred-file "%CRED_FILE%" setup --region "%REGION%" %VISIBLE_PW_FLAG%
if errorlevel 1 goto :fail

:run_prompt
echo.
set "QUEST_IP=auto"
set "QUEST_PORT=9000"
set /p QUEST_IP=Quest IP (default auto via OSCQuery):
if "%QUEST_IP%"=="" set "QUEST_IP=auto"
set /p QUEST_PORT=Quest port (default 9000):
if "%QUEST_PORT%"=="" set "QUEST_PORT=9000"

echo.
echo Starting Dexcom Share -> Quest bridge...
"%VENV_PY%" dexcom_share_to_quest3.py --cred-file "%CRED_FILE%" run --quest-ip "%QUEST_IP%" --quest-port "%QUEST_PORT%"
if errorlevel 1 goto :fail
exit /b 0

:fail
echo.
echo Bridge failed. Review the error above, then run this file again.
pause
exit /b 1
