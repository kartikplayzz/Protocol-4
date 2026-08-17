# -*- coding: utf-8 -*-
"""
================================================================================
  MAHARASHTRA POLICE HARDWARE KEY GENERATOR & SECURITY ANALYZER
================================================================================
Administrative tool for issuing, managing, and inspecting USB hardware dongles
for the Maharashtra Police & Legal Document Intelligence Studio.
"""

import os
import sys
import json
import time
from security_token_engine import (
    scan_connected_usb_drives,
    generate_police_dongle_token,
    write_key_to_usb,
    police_gate,
    DEFAULT_KEY_FILENAME
)

def interactive_cli():
    print("=" * 75)
    print("   MAHARASHTRA POLICE - HARDWARE KEY GENERATOR & USB SECURITY SUITE")
    print("=" * 75)
    
    print("\n[*] Scanning connected USB drives and removable hardware...")
    drives = scan_connected_usb_drives()
    
    if not drives:
        print("[!] No removable USB storage drives detected.")
        print("    Please insert a USB Flash Drive / Dongle and retry.")
        return

    print(f"\n[+] Detected {len(drives)} Storage Target(s):")
    for idx, d in enumerate(drives):
        s = d["suitability"]
        print(f"\n  [{idx + 1}] Drive {d['drive_letter']} ({d['model']})")
        print(f"      Hardware Serial:  {d['hardware_serial']}")
        print(f"      Suitability:      {s['grade']} (Score: {s['score_percent']}%)")
        print(f"      Recommendation:   {s['recommendation']}")
        print(f"      Key Installed:    {'YES (' + DEFAULT_KEY_FILENAME + ')' if d['has_key_file'] else 'NO'}")

    print("\n" + "-" * 75)
    print("Options:")
    print("  1. Issue New Hardware Key to a Drive")
    print("  2. Verify / Audit Existing Key on a Drive")
    print("  3. Exit")
    
    choice = input("\nEnter choice [1-3] (Default 1): ").strip() or "1"
    
    if choice == "1":
        drive_idx = input(f"Select target drive [1-{len(drives)}] (Default 1): ").strip() or "1"
        try:
            target_drive = drives[int(drive_idx) - 1]
        except Exception:
            target_drive = drives[0]

        print(f"\n[*] Generating Hardware Dongle for: {target_drive['drive_letter']} (Serial: {target_drive['hardware_serial']})")
        
        officer = input("Enter Officer Name (Default: Insp. R. K. Patil): ").strip() or "Insp. R. K. Patil"
        badge = input("Enter Officer Badge ID (Default: MH-POL-8842): ").strip() or "MH-POL-8842"
        station = input("Enter Police Station Code (Default: MUM-HQ-01): ").strip() or "MUM-HQ-01"
        clearance = int(input("Enter Clearance Level [1-5] (Default: 4): ").strip() or "4")
        allow_all = input("Allow key on ANY police workstation? [y/N] (Default y): ").strip().lower() in ["y", "yes", ""]

        token = generate_police_dongle_token(
            usb_serial=target_drive["hardware_serial"],
            officer_name=officer,
            badge_id=badge,
            station_code=station,
            clearance_level=clearance,
            allow_all_workstations=allow_all
        )

        ok, msg = write_key_to_usb(target_drive["mount_path"], token)
        if ok:
            print("\n" + "=" * 75)
            print("[+] SUCCESS! Physical Maharashtra Police Hardware Key created successfully!")
            print(f"    Target File:     {msg}")
            print(f"    Officer:         {officer} ({badge})")
            print(f"    Station:         {station}")
            print(f"    Security Score:  {token['key_security_score']}% (Cryptographically Signed)")
            print("=" * 75)
        else:
            print(f"\n[!] Failed writing key file: {msg}")

    elif choice == "2":
        drive_idx = input(f"Select drive to verify [1-{len(drives)}] (Default 1): ").strip() or "1"
        try:
            target_drive = drives[int(drive_idx) - 1]
        except Exception:
            target_drive = drives[0]

        print(f"\n[*] Auditing key on: {target_drive['drive_letter']}...")
        ok, msg, details = police_gate.verify_hardware_dongle(target_drive["mount_path"])
        if ok:
            print("\n[+] KEY VALID & AUTHENTICATED!")
            print(f"    Details: {json.dumps(details, indent=2)}")
        else:
            print(f"\n[!] Key Verification Failed: {msg}")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--auto-generate":
        # Headless generation for automated pipelines
        drives = scan_connected_usb_drives()
        if drives:
            t = drives[0]
            tok = generate_police_dongle_token(
                usb_serial=t["hardware_serial"],
                officer_name="Insp. R. K. Patil",
                badge_id="MH-POL-8842",
                station_code="MUM-HQ-01",
                clearance_level=4,
                allow_all_workstations=True
            )
            write_key_to_usb(t["mount_path"], tok)
            print("[+] Auto-generated default police key on:", t["drive_letter"])
    else:
        interactive_cli()
