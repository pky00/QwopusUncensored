@echo off
echo Setting up Qwopus chat client...

cd /d "%~dp0"

where python >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found. Install Python 3.10+ first.
    exit /b 1
)

if exist venv (
    echo Removing old venv...
    rmdir /s /q venv
)

echo Creating virtual environment...
python -m venv venv

echo Installing dependencies...
venv\Scripts\pip install PyQt6 requests

echo.
echo Setup complete. Run the chat with:
echo   %~dp0venv\Scripts\python.exe %~dp0chat.py
