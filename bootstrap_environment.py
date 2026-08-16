# -*- coding: utf-8 -*-
"""
Protocol-4 Self-Healing Bootstrap & Hardware Auto-Detection Engine
Detects hardware (CUDA/OpenCL/CPU), verifies packages & Tesseract, and auto-installs dependencies.
"""
import os
import sys
import subprocess
import json
import urllib.request
import multiprocessing

REQUIRED_PACKAGES = {
    "pymupdf": "pymupdf",
    "cv2": "opencv-python",
    "pytesseract": "pytesseract",
    "PIL": "pillow",
    "docx": "python-docx",
    "markitdown": "markitdown",
    "wordninja": "wordninja",
    "numpy": "numpy"
}

COMMON_TESSERACT_PATHS = [
    r"C:\Users\Kartikplayzz\AppData\Local\Programs\Tesseract-OCR\tesseract.exe",
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    os.path.expandvars(r"%LOCALAPPDATA%\Programs\Tesseract-OCR\tesseract.exe"),
    os.path.expandvars(r"%PROGRAMFILES%\Tesseract-OCR\tesseract.exe"),
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "tesseract", "tesseract.exe")
]

def check_internet_connection(timeout=3):
    """Checks if active internet connection is available."""
    try:
        urllib.request.urlopen("https://www.google.com", timeout=timeout)
        return True
    except Exception:
        try:
            urllib.request.urlopen("https://github.com", timeout=timeout)
            return True
        except Exception:
            return False

def detect_hardware():
    """Silently detects all GPU & CPU acceleration capabilities on any host PC."""
    hw = {
        "cpu_logical_cores": os.cpu_count() or 4,
        "gpu_available": False,
        "gpu_type": "None",
        "gpu_name": "None",
        "acceleration_backend": "CPU Multi-Threading",
        "optimal_worker_threads": 4
    }

    # 1. Check OpenCV OpenCL (Intel UHD/Iris, AMD Radeon, NVIDIA, Qualcomm)
    try:
        import cv2
        if cv2.ocl.haveOpenCL():
            cv2.ocl.setUseOpenCL(True)
            try:
                dev = cv2.ocl.Device.getDefault()
                hw["gpu_name"] = dev.name()
                hw["gpu_type"] = "OpenCL"
                hw["gpu_available"] = True
                hw["acceleration_backend"] = f"OpenCL GPU ({dev.name()})"
            except Exception:
                hw["gpu_name"] = "Generic OpenCL Device"
                hw["gpu_type"] = "OpenCL"
                hw["gpu_available"] = True
                hw["acceleration_backend"] = "OpenCL GPU Acceleration"
    except Exception:
        pass

    # 2. Check NVIDIA CUDA (if PyTorch or CUDA runtime is present)
    try:
        import torch
        if torch.cuda.is_available():
            hw["gpu_name"] = torch.cuda.get_device_name(0)
            hw["gpu_type"] = "CUDA"
            hw["gpu_available"] = True
            hw["acceleration_backend"] = f"NVIDIA CUDA ({torch.cuda.get_device_name(0)})"
    except Exception:
        pass

    # Dynamic thread optimization
    cores = hw["cpu_logical_cores"]
    if cores >= 12:
        hw["optimal_worker_threads"] = 8
    elif cores >= 8:
        hw["optimal_worker_threads"] = 6
    elif cores >= 4:
        hw["optimal_worker_threads"] = 4
    else:
        hw["optimal_worker_threads"] = max(2, cores)

    return hw

def find_tesseract_binary():
    """Discovers Tesseract OCR binary across system and local directory paths."""
    for p in COMMON_TESSERACT_PATHS:
        if os.path.exists(p):
            return p
    # Check PATH
    try:
        res = subprocess.check_output("where tesseract", shell=True, stderr=subprocess.DEVNULL).decode('utf-8').strip()
        if res and os.path.exists(res.splitlines()[0]):
            return res.splitlines()[0]
    except Exception:
        pass
    return None

def check_system_health():
    """Performs non-blocking comprehensive health check for portable execution."""
    health = {
        "all_ready": True,
        "installed_packages": [],
        "missing_packages": [],
        "tesseract_path": None,
        "has_tesseract": False,
        "has_marathi_model": False,
        "has_internet": False,
        "hardware": detect_hardware(),
        "paths": {
            "input_dir": r"E:\PDF" if os.path.exists(r"E:\PDF") else os.path.abspath("./workspace/PDF"),
            "output_dir": r"E:\PDF to MD" if os.path.exists(r"E:\PDF to MD") else os.path.abspath("./workspace/PDF to MD"),
            "archive_dir": r"E:\Completed PDF file Extraction" if os.path.exists(r"E:\Completed PDF file Extraction") else os.path.abspath("./workspace/Completed Archive")
        }
    }

    # 1. Check Python Packages
    for import_name, pip_name in REQUIRED_PACKAGES.items():
        try:
            __import__(import_name)
            health["installed_packages"].append(pip_name)
        except ImportError:
            health["missing_packages"].append(pip_name)
            health["all_ready"] = False

    # 2. Check Tesseract
    tess = find_tesseract_binary()
    if tess:
        health["tesseract_path"] = tess
        health["has_tesseract"] = True
        # Check tessdata directory for mar.traineddata
        tess_dir = os.path.dirname(tess)
        tessdata_dir = os.path.join(tess_dir, "tessdata")
        if os.path.exists(os.path.join(tessdata_dir, "mar.traineddata")):
            health["has_marathi_model"] = True
        else:
            health["all_ready"] = False
    else:
        health["has_tesseract"] = False
        health["all_ready"] = False

    # 3. Check Internet
    health["has_internet"] = check_internet_connection()

    return health

def auto_install_missing_dependencies(callback=None):
    """Auto-installs missing Python packages via pip and bootstraps missing assets."""
    health = check_system_health()
    missing = health["missing_packages"]
    results = {"installed": [], "failed": [], "success": True}

    if not missing:
        return {"success": True, "message": "All packages already installed.", "installed": []}

    if not health["has_internet"]:
        return {"success": False, "message": "No internet connection detected to install dependencies.", "missing": missing}

    for pkg in missing:
        if callback:
            callback(f"Installing {pkg}...")
        try:
            cmd = [sys.executable, "-m", "pip", "install", pkg, "--quiet", "--no-warn-script-location"]
            subprocess.check_call(cmd)
            results["installed"].append(pkg)
        except Exception as e:
            results["failed"].append(f"{pkg} ({str(e)})")
            results["success"] = False

    return results

if __name__ == "__main__":
    h = check_system_health()
    print("=== SYSTEM HEALTH & HARDWARE AUDIT ===")
    print(json.dumps(h, indent=2))
