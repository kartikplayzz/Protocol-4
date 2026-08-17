# -*- coding: utf-8 -*-
"""
Standalone Desktop Application Builder with Hardware Security Suite
"""
import os, subprocess, shutil

REPO_PATH = r"E:\Protocol-4"
DIST_DIR = os.path.join(REPO_PATH, "dist")
BUILD_DIR = os.path.join(REPO_PATH, "build")

# Clean old builds
if os.path.exists(BUILD_DIR):
    shutil.rmtree(BUILD_DIR, ignore_errors=True)

cmd = [
    "pyinstaller",
    "--noconfirm",
    "--onedir",
    "--windowed",
    "--name=Protocol4_Desktop",
    f"--icon={REPO_PATH}\\assets\\icon.ico",
    f"--add-data={REPO_PATH}\\web;web",
    f"--add-data={REPO_PATH}\\assets;assets",
    f"--add-data={REPO_PATH}\\server.py;.",
    f"--add-data={REPO_PATH}\\process_pdf_to_md.py;.",
    f"--add-data={REPO_PATH}\\bootstrap_environment.py;.",
    f"--add-data={REPO_PATH}\\security_token_engine.py;.",
    f"--add-data={REPO_PATH}\\usb_key_generator.py;.",
    f"--add-data={REPO_PATH}\\requirements.txt;.",
    "--hidden-import=pymupdf",
    "--hidden-import=fitz",
    "--hidden-import=pytesseract",
    "--hidden-import=docx",
    "--hidden-import=wordninja",
    "--hidden-import=security_token_engine",
    "--hidden-import=usb_key_generator",
    f"{REPO_PATH}\\desktop_app.py"
]

print("==================================================================")
print("  Compiling Protocol-4 Standalone Executable + Security Suite... ")
print("==================================================================")
res = subprocess.run(cmd, cwd=REPO_PATH, capture_output=True, text=True)
print("STDOUT:\n", res.stdout[-2000:] if len(res.stdout) > 2000 else res.stdout)
print("Compiler Exit Code:", res.returncode)

if res.returncode == 0:
    exe_path = os.path.join(DIST_DIR, "Protocol4_Desktop", "Protocol4_Desktop.exe")
    print(f"\n[+] SUCCESS! Standalone Executable compiled to: {exe_path}")
