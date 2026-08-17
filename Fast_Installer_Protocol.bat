@echo off
setlocal EnableDelayedExpansion
title Protocol-4: Automated Fast Installer & Environment Setup
color 0B

echo ==============================================================================
echo   MAHARASHTRA POLICE & LEGAL DOCUMENT INTELLIGENCE STUDIO
echo   Protocol-4 High-Speed Deployment & Dependency Setup Protocol
echo ==============================================================================
echo.

:: 1. Diagnostic Check: Python
python --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    color 0C
    echo [ERROR] Python 3.10+ is not detected in your system PATH!
    echo Please install Python 3.10+ from python.org and check "Add Python to PATH".
    pause
    exit /b 1
)

for /f "tokens=2" %%i in ('python --version 2^>^&1') do set PY_VER=%%i
echo [*] Detected Python Runtime: %PY_VER%

:: 2. Upgrade pip and install modern 2026/2025 dependencies with binary cache speedup
echo [*] Checking and installing modernized dependencies from requirements.txt...
python -m pip install --upgrade pip --quiet
python -m pip install -r requirements.txt --prefer-binary --upgrade --quiet
if %ERRORLEVEL% NEQ 0 (
    color 0E
    echo [WARNING] Some dependencies had warnings during installation, retrying with standard wheels...
    python -m pip install -r requirements.txt
)

:: 3. Run Self-Healing Hardware & Tesseract OCR Audit
echo [*] Executing System Health & Hardware Diagnostics...
python bootstrap_environment.py

:: 4. Build Silent Launcher VBS
set ROOT_DIR=%~dp0
set VBS_LAUNCHER=%ROOT_DIR%Protocol4_Launcher.vbs
(
    echo Set WshShell = CreateObject^("WScript.Shell"^)
    echo WshShell.CurrentDirectory = "%ROOT_DIR%"
    echo WshShell.Run "python desktop_app.py", 0, False
) > "%VBS_LAUNCHER%"

:: 5. Create Desktop Shortcut via VBScript
set MAKE_SHORTCUT=%ROOT_DIR%create_temp_sc.vbs
(
    echo Set oWS = WScript.CreateObject^("WScript.Shell"^)
    echo sLinkFile = oWS.SpecialFolders^("Desktop"^) ^& "\Protocol-4 Studio.lnk"
    echo Set oLink = oWS.CreateShortcut^(sLinkFile^)
    echo oLink.TargetPath = "%ROOT_DIR%dist\Protocol4_Desktop\Protocol4_Desktop.exe"
    echo oLink.WorkingDirectory = "%ROOT_DIR%"
    echo oLink.IconLocation = "%ROOT_DIR%assets\icon.ico, 0"
    echo oLink.Description = "Maharashtra Police and Legal Document Intelligence Studio"
    echo oLink.Save
) > "%MAKE_SHORTCUT%"

cscript //nologo "%MAKE_SHORTCUT%" >nul 2>&1
if exist "%MAKE_SHORTCUT%" del "%MAKE_SHORTCUT%"

echo.
echo ==============================================================================
echo [SUCCESS] Protocol-4 Studio Fast Installation Complete!
echo [SHORTCUT] Desktop shortcut created: "Protocol-4 Studio.lnk"
echo [STANDALONE] Executable: dist\Protocol4_Desktop\Protocol4_Desktop.exe
echo ==============================================================================
echo.
echo Launching Protocol-4 Studio...
start "" "%ROOT_DIR%dist\Protocol4_Desktop\Protocol4_Desktop.exe"
exit /b 0
