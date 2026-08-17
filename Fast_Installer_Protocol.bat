@echo off
setlocal enabledelayedexpansion
title Protocol-4 Legal Intelligence System - Fast Setup Protocol
color 0b

echo ==============================================================================
echo       PROTOCOL-4: MAHARASHTRA POLICE & LEGAL DOCUMENT INTELLIGENCE
echo                   Fast Automated Windows Setup Protocol
echo ==============================================================================
echo.

:: 1. Check Python Installation
echo [1/5] Checking Python Environment...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Python 3.10+ is required but not found in PATH!
    echo Please install Python from https://www.python.org and check "Add Python to PATH".
    echo.
    pause
    exit /b 1
)
for /f "tokens=*" %%v in ('python --version 2^>^&1') do echo     Found: %%v (Ready)

:: 2. Upgrade pip and install modern dependencies in high-speed parallel mode
echo.
echo [2/5] Installing & Updating Protocol-4 Dependencies...
python -m pip install --upgrade pip --quiet --no-warn-script-location
python -m pip install -r requirements.txt --prefer-binary --no-warn-script-location

:: 3. Hardware Acceleration & Tesseract Verification
echo.
echo [3/5] Auditing OCR Models & Hardware Acceleration (GPU/CPU)...
python bootstrap_environment.py

:: 4. Create Desktop & Start Menu Shortcuts
echo.
echo [4/5] Creating Windows Desktop & Start Menu Shortcuts...
set "SCRIPT_DIR=%~dp0"
set "LAUNCHER=%SCRIPT_DIR%Protocol4_Launcher.vbs"

:: Create silent background VBS launcher
(
    echo Set WshShell = CreateObject^("WScript.Shell"^)
    echo WshShell.CurrentDirectory = "%SCRIPT_DIR%"
    echo WshShell.Run "python desktop_app.py", 0, False
) > "%LAUNCHER%"

:: Create Desktop Shortcut using PowerShell
powershell -NoProfile -Command "$ws = New-Object -ComObject WScript.Shell; $s = $ws.CreateShortcut([System.IO.Path]::Combine([Environment]::GetFolderPath('Desktop'), 'Protocol-4 Studio.lnk')); $s.TargetPath = 'wscript.exe'; $s.Arguments = '\"%LAUNCHER%\"'; $s.WorkingDirectory = '%SCRIPT_DIR%'; $s.Description = 'Protocol-4 Legal & Police Intelligence Studio'; $icon = '%SCRIPT_DIR%assets\icon.ico'; if (Test-Path $icon) { $s.IconLocation = $icon }; $s.Save()"

echo     [+] Created Desktop Shortcut: 'Protocol-4 Studio.lnk'

:: 5. Launch Application
echo.
echo [5/5] Launching Protocol-4 Desktop Studio...
echo ==============================================================================
echo   Setup Complete! Starting Desktop Studio...
echo ==============================================================================
start "" wscript.exe "%LAUNCHER%"
exit /b 0
