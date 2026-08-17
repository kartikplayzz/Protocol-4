# -*- coding: utf-8 -*-
"""
Protocol-4 PyInstaller Standalone Windows Binary Compiler
Compiles desktop_app.py and bundles backend + web assets into dist/Protocol4_Desktop/
"""
import os
import sys
import subprocess
import shutil

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
WEB_DIR = os.path.join(ROOT_DIR, "web")
ASSETS_DIR = os.path.join(ROOT_DIR, "assets")
ICON_PATH = os.path.join(ASSETS_DIR, "icon.ico")

def build():
    print("==================================================================")
    print("  Compiling Protocol-4 Standalone Windows Desktop Executable...   ")
    print("==================================================================")

    server_file = os.path.join(ROOT_DIR, "server.py")
    process_file = os.path.join(ROOT_DIR, "process_pdf_to_md.py")
    bootstrap_file = os.path.join(ROOT_DIR, "bootstrap_environment.py")
    reqs_file = os.path.join(ROOT_DIR, "requirements.txt")
    entry_file = os.path.join(ROOT_DIR, "desktop_app.py")

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm",
        "--onedir",
        "--windowed",
        "--name", "Protocol4_Desktop",
        f"--add-data={WEB_DIR};web",
        f"--add-data={server_file};.",
        f"--add-data={process_file};.",
        f"--add-data={bootstrap_file};.",
        f"--add-data={reqs_file};.",
    ]

    if os.path.exists(ICON_PATH):
        cmd.append(f"--icon={ICON_PATH}")
        cmd.append(f"--add-data={ASSETS_DIR};assets")

    hidden_imports = [
        "pymupdf", "fitz", "cv2", "pytesseract", "PIL", "docx",
        "markitdown", "wordninja", "numpy", "webview", "pythonnet",
        "clr_loader", "http.server", "socketserver", "urllib.request"
    ]
    for hi in hidden_imports:
        cmd.extend(["--hidden-import", hi])

    cmd.append(entry_file)

    print("[*] Executing PyInstaller...")
    res = subprocess.call(cmd, cwd=ROOT_DIR)
    if res == 0:
        out_exe = os.path.join(ROOT_DIR, "dist", "Protocol4_Desktop", "Protocol4_Desktop.exe")
        print("\n[+] SUCCESS! Standalone Windows Desktop App compiled to:")
        print(f"    {out_exe}")
    else:
        print(f"\n[!] Build failed with exit code: {res}")

if __name__ == "__main__":
    build()
