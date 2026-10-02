@echo off
rem One-time setup for Ascensus ad Mathematica (needs internet once):
rem creates the Python environment, installs packages, makes the icon and the
rem "Ascensus ad Mathematica" shortcuts (project folder + Desktop). Play with the shortcut afterwards.
cd /d "%~dp0.."

if not exist ".venv\Scripts\pythonw.exe" (
    echo Creating Python environment...
    py -3.14 -m venv .venv || py -3.13 -m venv .venv || goto :fail
)
".venv\Scripts\python.exe" -m pip install -q -e . || goto :fail
if not exist "ascensus\assets\icon.ico" ".venv\Scripts\python.exe" tools\make_icon.py || goto :fail
powershell -NoProfile -ExecutionPolicy Bypass -File "tools\make_shortcut.ps1" || goto :fail
echo.
echo Done. Start the game with the "Ascensus ad Mathematica" shortcut.
pause
exit /b 0

:fail
echo.
echo Setup failed. Make sure Python 3.13 or newer is installed (https://www.python.org).
pause
exit /b 1
