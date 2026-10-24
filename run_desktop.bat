@echo off
title CleoStream — Desktop App
cd /d "%~dp0"

if not exist "venv\Scripts\python.exe" (
    echo [ERROR] Virtual environment not found in %~dp0venv.
    echo Please run: python -m venv venv and pip install -r requirements.txt
    pause
    exit /b 1
)

echo Starting CleoStream Desktop App...
start "" "venv\Scripts\python.exe" app.py %*
