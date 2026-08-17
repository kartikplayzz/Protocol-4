# -*- coding: utf-8 -*-
"""
Protocol-4 Full-Stack Windows Desktop Application
Native Windows WebView2 Desktop Client & Embedded Backend Pipeline Daemon
"""
import os
import sys
import time
import threading
import socket
import urllib.request
import webview

APP_DIR = os.path.dirname(os.path.abspath(__file__))
ICON_PATH = os.path.join(APP_DIR, "assets", "icon.ico")
if not os.path.exists(ICON_PATH):
    ICON_PATH = None

PORT = 8080
SERVER_URL = f"http://localhost:{PORT}"

def is_port_in_use(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('localhost', port)) == 0

def start_backend_server():
    """Starts the embedded server.py daemon in a background thread."""
    if is_port_in_use(PORT):
        print(f"[*] Port {PORT} is already active. Connecting to running daemon...")
        return

    print(f"[*] Starting embedded Protocol-4 backend server on port {PORT}...")
    try:
        import server
        server_thread = threading.Thread(target=server.run, kwargs={"port": PORT}, daemon=True)
        server_thread.start()
        
        for _ in range(25):
            time.sleep(0.2)
            try:
                with urllib.request.urlopen(f"{SERVER_URL}/api/status", timeout=1) as resp:
                    if resp.status == 200:
                        print("[+] Backend server is ready and responsive!")
                        return
            except Exception:
                pass
    except Exception as e:
        print(f"[!] Note on embedded server start: {e}")

class DesktopJsApi:
    """Native Python methods exposed directly to the Web UI via window.pywebview.api"""
    
    def select_pdf_files(self):
        """Opens native Windows file dialog to select PDF files and copy into incoming queue."""
        try:
            import tkinter as tk
            from tkinter import filedialog
            import shutil

            root = tk.Tk()
            root.withdraw()
            root.attributes('-topmost', True)
            
            file_paths = filedialog.askopenfilenames(
                title="Select PDF Documents to Extract",
                filetypes=[("PDF Documents", "*.pdf"), ("All Files", "*.*")]
            )
            root.destroy()

            if not file_paths:
                return {"success": False, "count": 0, "message": "No files selected"}

            input_dir = r"E:\PDF"
            os.makedirs(input_dir, exist_ok=True)
            copied = []

            for fp in file_paths:
                dest = os.path.join(input_dir, os.path.basename(fp))
                shutil.copy2(fp, dest)
                copied.append(os.path.basename(fp))

            return {
                "success": True,
                "count": len(copied),
                "files": copied,
                "message": f"Successfully queued {len(copied)} PDF file(s) into E:\\PDF\\"
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def open_output_folder(self):
        """Opens output directory directly in Windows Explorer."""
        target = r"E:\PDF to MD"
        os.makedirs(target, exist_ok=True)
        os.startfile(target)
        return {"success": True, "path": target}

    def open_archive_folder(self):
        """Opens archive directory in Windows Explorer."""
        target = r"E:\Completed PDF file Extraction"
        os.makedirs(target, exist_ok=True)
        os.startfile(target)
        return {"success": True, "path": target}

    def open_input_folder(self):
        """Opens input queue folder in Windows Explorer."""
        target = r"E:\PDF"
        os.makedirs(target, exist_ok=True)
        os.startfile(target)
        return {"success": True, "path": target}

def main():
    start_backend_server()
    api = DesktopJsApi()

    print("[*] Launching Protocol-4 Native Desktop Window...")
    window = webview.create_window(
        title="Protocol-4: Maharashtra Police & Legal Document Intelligence Studio",
        url=SERVER_URL,
        js_api=api,
        width=1320,
        height=860,
        min_size=(1024, 680),
        resizable=True,
        fullscreen=False,
        confirm_close=False,
        background_color='#0f172a'
    )

    webview.start(gui="edgechromium", debug=False)

if __name__ == "__main__":
    main()
