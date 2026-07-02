@echo off
setlocal

cd /d "%~dp0"

echo.
echo LeetCoach Windows Setup
echo -----------------------
echo This will create a local .venv, prepare local config files,
echo and add a LeetCoach shortcut to your Desktop.
echo.

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0installer\windows\install.ps1"

echo.
if errorlevel 1 (
  echo Setup failed. Please check the message above.
) else (
  echo Setup finished.
)
echo.
pause
