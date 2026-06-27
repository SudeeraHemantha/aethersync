@echo off
title AetherSync Setup Installer
echo ===================================================
echo             AETHERSYNC HUB SETUP INSTALLER
echo ===================================================
echo.

:: 1. Verify Python installation
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not added to your system PATH.
    echo Please install Python 3.10+ (and tick 'Add Python to PATH') before running setup.
    echo.
    pause
    exit /b
)

:: 2. Install library dependencies
echo [*] Installing required Python libraries (FastAPI, CustomTkinter, Uvicorn)...
python -m pip install --upgrade pip
python -m pip install customtkinter requests fastapi uvicorn python-multipart
if %errorlevel% neq 0 (
    echo [ERROR] Failed to install dependencies. Please check your internet connection.
    echo.
    pause
    exit /b
)
echo [+] Python dependencies installed successfully.
echo.

:: 3. Generate Desktop Shortcut & App Icon
echo [*] Initializing desktop shortcut configurations...
python desktop/setup_shortcut.py
if %errorlevel% neq 0 (
    echo [WARNING] Desktop shortcut generation encountered warnings.
)
echo.

echo ===================================================
echo   INSTALLATION COMPLETED! You can now start the
echo   AetherSync Hub from the shortcut on your desktop.
echo ===================================================
echo.
pause
