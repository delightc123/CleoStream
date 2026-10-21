@echo off
setlocal enabledelayedexpansion
title React in Meetings — Build Installer

cd /d "%~dp0"

echo ========================================================
echo   React in Meetings — Standalone Build System
echo ========================================================
echo.

if not exist "venv\Scripts\pyinstaller.exe" (
    echo [ERROR] PyInstaller not found in venv.
    echo Running: uv pip install pyinstaller --python venv\Scripts\python.exe
    uv pip install pyinstaller --python venv\Scripts\python.exe
)

echo [1/2] Compiling standalone package with PyInstaller...
"venv\Scripts\pyinstaller.exe" ReactInMeetings.spec --noconfirm
if errorlevel 1 (
    echo [ERROR] PyInstaller build failed.
    pause
    exit /b 1
)

echo.
echo [OK] PyInstaller build succeeded: dist\ReactInMeetings\
echo.

echo [2/2] Checking for Inno Setup compiler (ISCC.exe)...
set "ISCC="
if exist "%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe" set "ISCC=%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"
if exist "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" set "ISCC=C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
if exist "C:\Program Files\Inno Setup 6\ISCC.exe" set "ISCC=C:\Program Files\Inno Setup 6\ISCC.exe"
where ISCC.exe >nul 2>&1 && set "ISCC=ISCC.exe"

if defined ISCC (
    echo Compiling Windows Installer with: !ISCC!
    "!ISCC!" installer.iss
    if errorlevel 1 (
        echo [ERROR] Inno Setup compilation failed.
        pause
        exit /b 1
    )
    echo.
    echo ========================================================
    echo   BUILD SUCCESSFUL!
    echo   Installer: dist-installer\ReactInMeetings_Setup.exe
    echo ========================================================
) else (
    echo [NOTE] Inno Setup 6 is not installed on this local machine.
    echo Standalone binaries are ready in: dist\ReactInMeetings\
    echo.
    echo To build the single ReactInMeetings_Setup.exe installer:
    echo 1. Download Inno Setup 6: https://jrsoftware.org/isdl.php
    echo    -OR-
    echo 2. Push a git tag (e.g. v1.0.0) to GitHub, and GitHub Actions
    echo    will automatically compile and publish the installer!
)

echo.
pause
