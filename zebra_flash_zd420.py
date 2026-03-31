#!/usr/bin/env python3
"""
Flash ZD420 printer firmware from V77.x to V84.20.23Z.

Requires the printer to be connected via USB. The firmware is sent over the
USB endpoint directly -- no network connection needed.
"""

import usb.core
import os
import sys
import time
import zipfile

if os.geteuid() != 0:
    sys.stderr.write("pyusb this tool depends on requires root privileges, please run as root. Exiting...\n")
    sys.exit(1)

VENDOR_ID = 0x0a5f
PRODUCT_ID = 0x0120
FIRMWARE_ZIP = os.path.join(os.path.dirname(os.path.abspath(__file__)), "firmware", "V84.20.23Z.zip")
FIRMWARE_ZPL = "V84.20.23Z.zpl"

device = usb.core.find(idVendor=VENDOR_ID, idProduct=PRODUCT_ID)

if device is None:
    sys.stderr.write("Could not find ZD420 printer attached. Exiting...\n")
    sys.exit(1)

if device.is_kernel_driver_active(0):
    print("Detaching kernel driver...")
    device.detach_kernel_driver(0)

config = device.get_active_configuration()
interface = config[(0, 0)]
out_endpoint = interface[0]
in_endpoint = interface[1]

# Check current firmware version
try:
    # Drain pending data
    try:
        while True:
            in_endpoint.read(8192, timeout=500)
    except:
        pass

    out_endpoint.write(b'! U1 getvar "appl.name"\r\n')
    time.sleep(1)
    response = in_endpoint.read(4096, timeout=3000)
    current_fw = bytes(response).decode('utf-8', errors='ignore').strip().strip('"')
    print(f"Current firmware: {current_fw}")

    if current_fw.startswith("V84"):
        print(f"Printer is already on V84 firmware ({current_fw}). No upgrade needed.")
        sys.exit(0)
except (usb.core.USBError, Exception):
    print("WARNING: Could not read firmware version, proceeding anyway...")
    current_fw = "unknown"

# Extract firmware from zip
if not os.path.exists(FIRMWARE_ZIP):
    sys.stderr.write(f"Firmware zip not found at {FIRMWARE_ZIP}. Exiting...\n")
    sys.exit(1)

print(f"Extracting {FIRMWARE_ZPL} from {FIRMWARE_ZIP}...")
with zipfile.ZipFile(FIRMWARE_ZIP, 'r') as zf:
    if FIRMWARE_ZPL not in zf.namelist():
        sys.stderr.write(f"{FIRMWARE_ZPL} not found in zip archive. Exiting...\n")
        sys.exit(1)
    firmware_data = zf.read(FIRMWARE_ZPL)

firmware_size = len(firmware_data)
print(f"Firmware size: {firmware_size} bytes ({firmware_size / 1024 / 1024:.1f} MB)")

print(f"\nThis will upgrade the ZD420 from {current_fw} to V84.20.23Z.")
confirm = input("Proceed? [y/N]: ")
if confirm.lower() != 'y':
    print("Aborted.")
    sys.exit(0)

# Send firmware in chunks with generous timeout
CHUNK_SIZE = 8192
WRITE_TIMEOUT = 30000  # 30 seconds per chunk
total_chunks = (firmware_size + CHUNK_SIZE - 1) // CHUNK_SIZE
sent = 0
last_pct = -1

print(f"Sending firmware ({total_chunks} chunks)... this will take a few minutes.")
try:
    for i in range(0, firmware_size, CHUNK_SIZE):
        chunk = firmware_data[i:i + CHUNK_SIZE]
        out_endpoint.write(chunk, timeout=WRITE_TIMEOUT)
        sent += len(chunk)
        pct = int(sent * 100 / firmware_size)
        if pct >= last_pct + 10:
            print(f"  {pct}% ({sent}/{firmware_size})")
            last_pct = pct
    print("  100% -- all data sent.")
except usb.core.USBError as e:
    if sent > firmware_size * 0.9:
        # Most data sent, printer likely started flashing
        print(f"\n  USB connection closed at {sent * 100 / firmware_size:.0f}% ({e})")
        print("  Printer is likely flashing firmware.")
    else:
        sys.stderr.write(f"\nERROR: Transfer failed at {sent * 100 / firmware_size:.0f}% ({e})\n")
        sys.stderr.write("Try again or use FTP method (see FIRMWARE_UPGRADE.md).\n")
        sys.exit(1)

print(f"""
Firmware sent. The printer is now flashing and will reboot.
This process takes 2-3 minutes. Do NOT power off the printer.

After reboot, verify the firmware version:
  sudo .venv3/bin/python3 zebra_flash_zd420.py

Then provision with:
  sudo .venv3/bin/python3 zebra_wifi_setup.py
""")
