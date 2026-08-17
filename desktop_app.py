# -*- coding: utf-8 -*-
"""
================================================================================
  MAHARASHTRA POLICE & LEGAL DOCUMENT INTELLIGENCE STUDIO
  DESKTOP APPLICATION CORE & 2FA HARDWARE DONGLE GATE (PROTOCOL-4)
================================================================================
"""

import os
import sys
import time
import threading
import subprocess
import webview
from security_token_engine import (
    police_gate,
    scan_connected_usb_drives,
    generate_police_dongle_token,
    write_key_to_usb,
    is_debugger_attached,
    get_machine_uuid
)

APP_TITLE = "Maharashtra Police & Legal Document Intelligence Studio"
SERVER_PORT = 8080
SERVER_URL = f"http://127.0.0.1:{SERVER_PORT}"
ASSETS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
ICON_PATH = os.path.join(ASSETS_DIR, "icon.ico")

def is_server_running(url, timeout=1.0):
    import urllib.request
    try:
        req = urllib.request.Request(f"{url}/api/system/check-health", headers={"User-Agent": "Protocol4-Desktop"})
        with urllib.request.urlopen(req, timeout=timeout) as res:
            return res.status == 200
    except Exception:
        return False

def start_server_daemon():
    if is_server_running(SERVER_URL):
        print(f"[*] Server daemon already active on port {SERVER_PORT}")
        return None

    server_script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "server.py")
    if not os.path.exists(server_script):
        server_script = r"E:\Protocol-4\server.py"

    print(f"[*] Starting background server daemon: {server_script}")
    import importlib.util
    spec = importlib.util.spec_from_file_location("server_daemon", server_script)
    server_mod = importlib.util.module_from_spec(spec)
    
    t = threading.Thread(target=spec.loader.exec_module, args=(server_mod,), daemon=True)
    t.start()

    # Wait for server ready
    for _ in range(30):
        if is_server_running(SERVER_URL):
            print(f"[+] Server daemon confirmed running on {SERVER_URL}")
            return t
        time.sleep(0.2)
    return t

class DesktopJsApi:
    """Bridge for JavaScript to invoke native Windows dialogs and Police Security functions."""
    
    def __init__(self):
        self._window = None

    def set_window(self, window):
        self._window = window

    # --- File Dialog Bridges ---
    def select_pdf_files(self):
        if not self._window:
            return []
        res = self._window.create_file_dialog(
            webview.OPEN_DIALOG,
            allow_multiple=True,
            file_types=('PDF & Word Documents (*.pdf;*.docx)', 'All Files (*.*)')
        )
        return list(res) if res else []

    def open_input_folder(self):
        os.startfile(r"E:\PDF")
        return True

    def open_output_folder(self):
        os.startfile(r"E:\PDF to MD")
        return True

    def open_archive_folder(self):
        os.startfile(r"E:\Completed PDF file Extraction")
        return True

    # --- Hardware Dongle Security Bridges ---
    def get_security_status(self):
        drives = scan_connected_usb_drives()
        has_key = any(d.get("has_key_file") for d in drives)
        return {
            "is_locked_down": police_gate.is_locked_down,
            "is_authenticated": (police_gate.active_session_token is not None),
            "has_valid_dongle": has_key,
            "connected_drives": drives,
            "failed_attempts": police_gate.failed_attempts,
            "max_attempts": police_gate.max_failed_attempts,
            "machine_uuid": get_machine_uuid(),
            "anti_debugger_clean": not is_debugger_attached()
        }

    def unlock_with_dongle(self, password, drive_path=None):
        ok, msg, details = police_gate.full_2fa_unlock(password, drive_path)
        return {
            "success": ok,
            "message": msg,
            "details": details,
            "is_locked_down": police_gate.is_locked_down
        }

    def generate_usb_key(self, drive_letter, officer_name, badge_id, station_code, clearance=4):
        clean_drive = drive_letter.rstrip('\\') + '\\'
        drives = scan_connected_usb_drives()
        matched_serial = "VOL-DEFAULT"
        for d in drives:
            if d["drive_letter"].upper() == clean_drive.upper().rstrip('\\') + ':':
                matched_serial = d["hardware_serial"]
                break

        tok = generate_police_dongle_token(
            usb_serial=matched_serial,
            officer_name=officer_name,
            badge_id=badge_id,
            station_code=station_code,
            clearance_level=int(clearance),
            allow_all_workstations=True
        )
        ok, path_or_err = write_key_to_usb(clean_drive, tok)
        return {
            "success": ok,
            "target_file": path_or_err if ok else "",
            "error": path_or_err if not ok else "",
            "security_score": tok.get("key_security_score", 95)
        }

def launch_desktop_app():
    # 1. Anti-Debugger Check at Boot
    if is_debugger_attached():
        print("[!] SECURITY HALT: Unauthorized Debugger / Memory Inspector Detected.")
        sys.exit(1)

    # 2. Start Embedded Server Daemon
    start_server_daemon()

    # 3. Create Native JS API Bridge
    api = DesktopJsApi()

    # 4. Configure Native Edge Chromium Window
    window = webview.create_window(
        title=APP_TITLE,
        url=SERVER_URL,
        js_api=api,
        width=1340,
        height=880,
        min_size=(1024, 700),
        frameless=False,
        easy_drag=True
    )
    api.set_window(window)

    print("[*] Launching Maharashtra Police Desktop Studio (WebView2 Chromium Engine)...")
    webview.start(debug=False, icon=ICON_PATH if os.path.exists(ICON_PATH) else None)

if __name__ == "__main__":
    launch_desktop_app()
