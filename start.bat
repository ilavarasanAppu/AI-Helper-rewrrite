@echo off
cd /d "%~dp0"
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
set PYTHON_EXE=
set PYTHONW_EXE=
if exist "%LOCALAPPDATA%\Programs\Python\Python314\python.exe" (
    set PYTHON_EXE=%LOCALAPPDATA%\Programs\Python\Python314\python.exe
    set PYTHONW_EXE=%LOCALAPPDATA%\Programs\Python\Python314\pythonw.exe
) else if exist "%USERPROFILE%\AppData\Local\hermes\hermes-agent\venv\Scripts\python.exe" (
    set PYTHON_EXE=%USERPROFILE%\AppData\Local\hermes\hermes-agent\venv\Scripts\python.exe
    set PYTHONW_EXE=%USERPROFILE%\AppData\Local\hermes\hermes-agent\venv\Scripts\pythonw.exe
) else (
    where python >nul 2>&1 && set PYTHON_EXE=python || set PYTHONW_EXE=pythonw
)
if not defined PYTHON_EXE (echo ERROR: Python not found & pause & exit /b 1)
echo Starting Win AI Helper...
%PYTHON_EXE% %~dp0main.py
if errorlevel 1 (echo. & echo ERROR: App failed to start. & pause & exit /b 1)
exit
