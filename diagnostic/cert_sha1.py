#!/usr/bin/env python3

import usb.core
import os
import sys
import time
from ftplib import FTP

if os.geteuid() != 0:
    sys.stderr.write("Requires root. Exiting...\n")
    sys.exit(1)

VENDOR_ID = 0x0a5f
PRODUCT_ID = 0x0120
PRINTER_IP = "192.168.1.118"
PEM_PATH = "./ssl/rootCA.crt"

device = usb.core.find(idVendor=VENDOR_ID, idProduct=PRODUCT_ID)
if device is None:
    sys.stderr.write("Printer not found. Exiting...\n")
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

# Step 1: Delete old cert
print("=== Step 1: Delete old cert ===")
out_ep.write(b'! U1 do "file.delete" "E:WEBLINK1_CA.NRD"\r\n')
time.sleep(1)
drain()

# Step 2: Disable FTP execute_file
print("\n=== Step 2: Disable FTP execute_file ===")
out_ep.write(b'! U1 setvar "ip.ftp.execute_file" "off"\r\n')
time.sleep(1)

# Step 3: Upload new SHA1 root CA via FTP
print("\n=== Step 3: Upload SHA1 root CA via FTP ===")
ftp = FTP(PRINTER_IP)
ftp.login()
with open(PEM_PATH, "rb") as f:
    result = ftp.storbinary("STOR WEBLINK1_CA.NRD", f)
    print(f"  STOR: {result}")
ftp.retrlines('LIST')
ftp.quit()

# Step 4: Re-enable execute_file
print("\n=== Step 4: Re-enable FTP execute_file ===")
out_ep.write(b'! U1 setvar "ip.ftp.execute_file" "on"\r\n')
time.sleep(1)

# Step 5: Change weblink URL to port 8499
print("\n=== Step 5: Update weblink URL to port 8499 ===")
out_ep.write(b'! U1 setvar "weblink.ip.conn1.location" "https://zserver.hallochef.net:8499/"\r\n')
time.sleep(1)
print(f"weblink.ip.conn1.location = {query('weblink.ip.conn1.location')}")

# Step 6: Verify cert on printer
print("\n=== Step 6: Verify cert on printer ===")
out_ep.write(b"^XA^HWE:*.NRD^XZ")
time.sleep(2)
drain()

# Step 7: Reset printer
print("\n=== Step 7: Reset printer ===")
out_ep.write(b'! U1 setvar "device.reset" "true"\r\n')
print("Reset sent.")
