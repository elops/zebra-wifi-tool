#!/usr/bin/env python3

import usb.core
import os
import sys
import time

if os.geteuid() != 0:
    sys.stderr.write("Requires root. Exiting...\n")
    sys.exit(1)

VENDOR_ID = 0x0a5f
PRODUCT_ID = 0x0120

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
                print(f"  >> {text[:800]}")
    except:
        pass

def query(var):
    cmd = f'! U1 getvar "{var}"\r\n'
    out_ep.write(cmd.encode('utf-8'))
    time.sleep(1)
    try:
        response = in_ep.read(8192, timeout=5000)
        return bytes(response).decode('utf-8', errors='ignore').strip()
    except:
        return "<timeout>"

# Drain pending
drain()

# Step 1: Check printer time
print("=== Step 1: Check printer clock ===")
print(f"rtc.date = {query('rtc.date')}")
print(f"rtc.time = {query('rtc.time')}")
print(f"rtc.timezone = {query('rtc.timezone')}")

# Step 2: Check cert-related info
print("\n=== Step 2: Check cert info ===")
print(f"file.cert.expiration = {query('file.cert.expiration')}")

# Step 3: Delete old cert files and re-upload with correct ~DY syntax
print("\n=== Step 3: Delete old cert files ===")
old_files = [
    "E:WEBLINK1_CA.NRD",
    "E:SSL_CA.NRD",
    "E:TRUSTED_CERTS.NRD",
    "E:WEBLINK1_CA.DER",
    "E:CA_CERT.NRD",
    "E:WEBLINK1_CA.PEM",
    "E:CA.PEM",
    "E:CONN1_CA.NRD",
]
for f in old_files:
    cmd = f"! U1 do \"file.delete\" \"{f}\"\r\n"
    print(f"  Deleting {f}...")
    out_ep.write(cmd.encode('utf-8'))
    time.sleep(0.5)
    drain()

# Step 4: Upload cert with corrected ~DY syntax
print("\n=== Step 4: Upload CA cert ===")
pem_path = "./ssl/rootCA.crt"
with open(pem_path, "r") as f:
    pem_data = f.read().strip()

pem_bytes = pem_data.encode('utf-8')
pem_size = len(pem_bytes)
print(f"PEM cert size: {pem_size} bytes")

# Method A: ~DY with .NRD extension in filename, B,P format (PEM)
print("\n  Method A: ~DYE:WEBLINK1_CA.NRD,B,P,{pem_size},0,<data>")
dy_cmd_a = f"~DYE:WEBLINK1_CA.NRD,B,P,{pem_size},0,{pem_data}\r\n"
out_ep.write(dy_cmd_a.encode('utf-8'))
time.sleep(3)
drain()

# Step 5: Verify file exists
print("\n=== Step 5: Verify cert on printer ===")
out_ep.write(b"^XA^HWE:*.NRD^XZ")
time.sleep(2)
drain()

# Step 6: Check cert expiration (to see if printer recognizes it)
print("\n=== Step 6: Check if printer recognizes cert ===")
print(f"file.cert.expiration = {query('file.cert.expiration')}")

# Step 7: Reset printer to reload certs
print("\n=== Step 7: Resetting printer ===")
out_ep.write(b'! U1 setvar "device.reset" "true"\r\n')
print("Reset command sent. Printer rebooting...")
