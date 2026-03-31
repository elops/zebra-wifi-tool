#!/usr/bin/env python3

import usb.core
import os
import sys
import time
import subprocess
from ftplib import FTP

if os.geteuid() != 0:
    sys.stderr.write("Requires root. Exiting...\n")
    sys.exit(1)

VENDOR_ID = 0x0a5f
PRODUCT_ID = 0x0120
PRINTER_IP = "192.168.1.118"
PEM_PATH = "./ssl/rootCA.crt"
DER_PATH = "/tmp/rootCA.der"

# Convert PEM to DER
subprocess.run(["openssl", "x509", "-in", PEM_PATH, "-outform", "DER", "-out", DER_PATH], check=True)

device = usb.core.find(idVendor=VENDOR_ID, idProduct=PRODUCT_ID)
if device is None:
    sys.stderr.write("Could not find Zebra printer attached. Exiting...\n")
    sys.exit(1)

if device.is_kernel_driver_active(0):
    device.detach_kernel_driver(0)

config = device.get_active_configuration()
interface = config[(0, 0)]
out_ep = interface[0]
in_ep = interface[1]

def drain():
    try:
        while True:
            resp = in_ep.read(8192, timeout=2000)
            text = bytes(resp).decode('utf-8', errors='ignore').strip()
            if text:
                print(f"  >> {text[:500]}")
    except:
        pass

def query(var):
    cmd = f'! U1 getvar "{var}"\r\n'
    out_ep.write(cmd.encode('utf-8'))
    time.sleep(1.5)
    try:
        response = in_ep.read(8192, timeout=5000)
        return bytes(response).decode('utf-8', errors='ignore').strip()
    except:
        return "<timeout>"

drain()

# Step 1: Disable execute_file and enable FTP
print("=== Step 1: Configure FTP ===")
out_ep.write(b'! U1 setvar "ip.ftp.enable" "on"\r\n')
time.sleep(0.5)
out_ep.write(b'! U1 setvar "ip.ftp.execute_file" "off"\r\n')
time.sleep(1)
drain()

# Step 2: Delete old cert via USB
print("\n=== Step 2: Delete old cert ===")
out_ep.write(b'! U1 do "file.delete" "E:WEBLINK1_CA.NRD"\r\n')
time.sleep(1)
drain()

# Step 3: Upload cert via FTP
print("\n=== Step 3: Upload cert via FTP ===")
try:
    ftp = FTP(PRINTER_IP)
    ftp.login()
    print(f"  FTP connected to {PRINTER_IP}")

    # List files
    print("  Files before upload:")
    ftp.retrlines('LIST *CA*')

    # Upload PEM version
    print(f"\n  Uploading PEM as WEBLINK1_CA.NRD...")
    with open(PEM_PATH, "rb") as f:
        ftp.storbinary("STOR WEBLINK1_CA.NRD", f)
    print("  PEM upload done")

    # Verify
    print("  Files after PEM upload:")
    ftp.retrlines('LIST *CA*')

    ftp.quit()
    print("  FTP session closed")

except Exception as e:
    print(f"  FTP error: {e}")

# Step 4: Re-enable execute_file
print("\n=== Step 4: Re-enable execute_file ===")
out_ep.write(b'! U1 setvar "ip.ftp.execute_file" "on"\r\n')
time.sleep(1)
drain()

# Step 5: Reset printer
print("\n=== Step 5: Reset printer ===")
out_ep.write(b'! U1 setvar "device.reset" "true"\r\n')
print("Reset sent. Waiting 20s for reboot...")
time.sleep(20)

# Reconnect
device = usb.core.find(idVendor=VENDOR_ID, idProduct=PRODUCT_ID)
if device is None:
    print("Printer not found after reset, waiting more...")
    time.sleep(15)
    device = usb.core.find(idVendor=VENDOR_ID, idProduct=PRODUCT_ID)

if device is None:
    print("Printer still not found. Check manually.")
    sys.exit(1)

if device.is_kernel_driver_active(0):
    device.detach_kernel_driver(0)

config = device.get_active_configuration()
interface = config[(0, 0)]
out_ep = interface[0]
in_ep = interface[1]
drain()

# Step 6: Check weblink logs
print("\n=== Step 6: Check weblink connection status ===")
time.sleep(5)  # Give it time to attempt connection
print(f"weblink.ip.conn1.num_connections = {query('weblink.ip.conn1.num_connections')}")

print("\n=== Weblink logs ===")
result = query("weblink.logging.entries")
print(result)
