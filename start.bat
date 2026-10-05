@echo off
REM ============================================================
REM  Win AI Helper - Background Launcher
REM  - Launches main.py with pythonw (no console window)
REM  - Detached via START so closing this terminal wont kill it
REM  - Use stop.bat to terminate the running instance
REM ============================================================
cd /d "%~dp0"
set PYTHONUTF8=1
set PYTHONW_EXE=
if exist "%LOCALAPPDATA%\Programs\Python\Python314\pythonw.exe" (
    set PYTHONW_EXE=%LOCALAPPDATA%\Programs\Python\Python314\pythonw.exe
) else if exist "%USERPROFILE%\AppData\Local\hermes\hermes-agent\venv\Scripts\pythonw.exe" (
    set PYTHONW_EXE=%USERPROFILE%\AppData\Local\hermes\hermes-agent\venv\Scripts\pythonw.exe
) else (
    where pythonw >nul 2>&1 && set PYTHONW_EXE=pythonw
)
if not defined PYTHONW_EXE (echo ERROR: pythonw not found & pause & exit /b 1)
echo Starting Win AI Helper in background...
start "" "%PYTHONW_EXE%" "%~dp0main.py"
if errorlevel 1 (echo. & echo ERROR: App failed to start. & pause & exit /b 1)
echo Win AI Helper is running in the system tray.
echo Run stop.bat to terminate it.
exit
