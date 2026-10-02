@echo off
REM ============================================================
REM  ⚡ Win AI Helper — One-Click Background Launcher
REM  - Auto-checks dependencies
REM  - Auto-starts Ollama if needed
REM  - Runs application detached in background via pythonw
REM  - Keeps terminal open on error so you can see the message
REM ============================================================

cd /d "%~dp0"

set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"

REM — Locate Python & Pythonw Executable ————————————————————————
set "PYTHON_EXE="
set "PYTHONW_EXE="

if exist "%LOCALAPPDATA%\Programs\Python\Python314\python.exe" (
    set "PYTHON_EXE=%LOCALAPPDATA%\Programs\Python\Python314\python.exe"
    set "PYTHONW_EXE=%LOCALAPPDATA%\Programs\Python\Python314\pythonw.exe"
) else if exist "%USERPROFILE%\AppData\Local\hermes\hermes-agent\venv\Scripts\python.exe" (
    set "PYTHON_EXE=%USERPROFILE%\AppData\Local\hermes\hermes-agent\venv\Scripts\python.exe"
    set "PYTHONW_EXE=%USERPROFILE%\AppData\Local\hermes\hermes-agent\venv\Scripts\pythonw.exe"
) else (
    REM Try to find python in PATH
    where python >nul 2>&1 && set "PYTHON_EXE=python" || set "PYTHON_EXE="
    where pythonw >nul 2>&1 && set "PYTHONW_EXE=pythonw" || set "PYTHONW_EXE="
)

REM Fallback: if pythonw not found, use python.exe
if not defined PYTHONW_EXE (
    if defined PYTHON_EXE (
        set "PYTHONW_EXE=%PYTHON_EXE%"
    ) else (
        echo [ERROR] Python not found. Please install Python 3.10+ and try again.
        echo.
        echo Press any key to close...
        pause >nul
        exit /b 1
    )
)

if not defined PYTHON_EXE (
    echo [ERROR] Python not found. Please install Python 3.10+ and try again.
    echo.
    echo Press any key to close...
    pause >nul
    exit /b 1
)

REM — Verify Python Works ————————————————————————————————
"%PYTHON_EXE%" --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python found but not working. Try reinstalling Python 3.10+.
    echo.
    pause
    exit /b 1
)

REM — Check & Install Dependencies if Missing ——————————————————
if exist "requirements.txt" (
    "%PYTHON_EXE%" -c "import PySide6" >nul 2>&1
    if %errorlevel% neq 0 (
        echo [i] Installing required packages...
        "%PYTHON_EXE%" -m pip install -r requirements.txt --quiet
        if %errorlevel% neq 0 (
            echo [ERROR] Failed to install dependencies.
            echo.
            pause
            exit /b 1
        )
    )
)

REM — Verify PySide6 has QAction in QtGui (PySide6 6.8+ fix) ——
"%PYTHON_EXE%" -c "from PySide6.QtGui import QAction" >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] PySide6 install is broken or too old. Reinstalling...
    "%PYTHON_EXE%" -m pip install --upgrade --force-reinstall PySide6
    if %errorlevel% neq 0 (
        echo [ERROR] Could not fix PySide6. Check your internet connection.
        echo.
        pause
        exit /b 1
    )
)

REM — Ensure Ollama Server is Running ——————————————————————————
where ollama >nul 2>&1
if %errorlevel% equ 0 (
    ollama list >nul 2>&1
    if %errorlevel% neq 0 (
        start /min "" ollama serve
        ping 127.0.0.1 -n 3 >nul 2>&1
    )
)

REM — Launch Application Detached in Background ————————————————
start "" "%PYTHONW_EXE%" "%~dp0main.py"

REM — Close Terminal Window Immediately ————————————————————————
REM The app runs in background via pythonw (no console window).
REM If you got here, everything is fine — the app is now running in the tray.
exit