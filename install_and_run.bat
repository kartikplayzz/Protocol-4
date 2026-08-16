@echo off
title Protocol-4 Legal Intelligence System Launcher
echo ======================================================================
echo   PROTOCOL-4: Maharashtra Police & Legal Document Extraction Suite
echo ======================================================================
echo.

:: 1. Check Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python 3.10+ is required but not found in PATH!
    echo Please install Python from https://www.python.org and add to PATH.
    pause
    exit /b 1
)

:: 2. Auto-Install Dependencies
echo [1/3] Verifying and installing architecture dependencies...
python -m pip install -r requirements.txt --quiet --no-warn-script-location

:: 3. Run Self-Healing Hardware & Environment Audit
echo [2/3] Auditing hardware acceleration (GPU/CPU) & Tesseract models...
python bootstrap_environment.py

:: 4. Start Server Daemon & Open Browser
echo [3/3] Starting Protocol-4 Web Studio Server...
start "" "http://localhost:8080"
python server.py
pause
