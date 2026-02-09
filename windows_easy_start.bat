@echo off
setlocal enableextensions
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo Creating local virtual environment...
  where py >nul 2>nul
  if errorlevel 1 (
    where python >nul 2>nul
    if errorlevel 1 (
      echo Python 3 is not installed or not on PATH.
      echo Install from https://www.python.org/downloads/windows/
      pause
      exit /b 1
    )
    python -m venv .venv
  ) else (
    py -3 -m venv .venv
  )
  if errorlevel 1 goto :fail
)

set "VENV_PY=.venv\Scripts\python.exe"

"%VENV_PY%" -c "import cryptography, pythonosc, pydexcom, zeroconf" >nul 2>nul
if errorlevel 1 (
  echo Installing dependencies...
  "%VENV_PY%" -m pip install --upgrade pip
  if errorlevel 1 goto :fail

  "%VENV_PY%" -m pip install -r requirements.txt
  if errorlevel 1 (
    echo Standard install failed. Trying pydexcom GitHub fallback...
    "%VENV_PY%" -m pip install python-osc cryptography zeroconf "git+https://github.com/gagebenne/pydexcom"
    if errorlevel 1 goto :fail
  )
)

if defined APPDATA (
  set "CRED_FILE=%APPDATA%\dexcom-osc-bridge\dexcom_credentials.json"
) else (
  set "CRED_FILE=%USERPROFILE%\AppData\Roaming\dexcom-osc-bridge\dexcom_credentials.json"
)

if not exist "%CRED_FILE%" (
  echo.
  echo First-time setup: encrypted Dexcom credentials not found.
  set "REGION=us"
  set /p REGION=Enter region [us/ous/jp] (default us):
  if "%REGION%"=="" set "REGION=us"

  "%VENV_PY%" dexcom_share_to_quest3.py setup --cred-file "%CRED_FILE%" --region "%REGION%"
  if errorlevel 1 goto :fail
)

echo.
set "QUEST_IP=auto"
set "QUEST_PORT=9000"
set /p QUEST_IP=Quest IP (default auto via OSCQuery):
if "%QUEST_IP%"=="" set "QUEST_IP=auto"
set /p QUEST_PORT=Quest port (default 9000):
if "%QUEST_PORT%"=="" set "QUEST_PORT=9000"

echo.
echo Starting Dexcom Share -> Quest bridge...
"%VENV_PY%" dexcom_share_to_quest3.py run --cred-file "%CRED_FILE%" --quest-ip "%QUEST_IP%" --quest-port "%QUEST_PORT%"
if errorlevel 1 goto :fail
exit /b 0

:fail
echo.
echo Bridge failed. Review the error above, then run this file again.
pause
exit /b 1
