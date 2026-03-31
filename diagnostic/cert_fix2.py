#!/usr/bin/env python3

import usb.core
import os
import sys
import time
import subprocess

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
    collected = ""
    try:
        while True:
            resp = in_ep.read(8192, timeout=2000)
            text = bytes(resp).decode('utf-8', errors='ignore').strip()
            if text:
                collected += text
                print(f"  >> {text[:800]}")
    except:
        pass
    return collected

def query(var):
    cmd = f'! U1 getvar "{var}"\r\n'
    out_ep.write(cmd.encode('utf-8'))
    time.sleep(1.5)
    try:
        response = in_ep.read(8192, timeout=5000)
        return bytes(response).decode('utf-8', errors='ignore').strip()
    except:
        return "<timeout>"

# Drain pending
drain()

# Wait for printer to be ready after previous reset
print("Waiting for printer to be ready...")
time.sleep(15)
drain()

pem_path = "./ssl/rootCA.crt"

# Convert to DER
der_path = "/tmp/rootCA.der"
subprocess.run(["openssl", "x509", "-in", pem_path, "-outform", "DER", "-out", der_path], check=True)

with open(pem_path, "r") as f:
    pem_data = f.read().strip()
pem_bytes = pem_data.encode('utf-8')

with open(der_path, "rb") as f:
    der_data = f.read()

print(f"PEM size: {len(pem_bytes)}, DER size: {len(der_data)}")

# === Method 1: Original working ~DY with PEM (re-upload to confirm) ===
print("\n=== Method 1: Re-upload PEM with original syntax ===")
dy1 = f"~DYE:WEBLINK1_CA,B,NRD,{len(pem_bytes)},,{pem_data}\n"
out_ep.write(dy1.encode('utf-8'))
time.sleep(3)
drain()

# Check it's there
print("Checking file...")
resp = query("file.dir")
if "WEBLINK1_CA.NRD" in resp:
    print("  WEBLINK1_CA.NRD found (PEM upload OK)")
else:
    print(f"  File listing: {resp[:200]}")

# === Method 2: Try DER format with same naming ===
# First delete PEM version
print("\n=== Method 2: Upload DER format ===")
out_ep.write(b'! U1 do "file.delete" "E:WEBLINK1_CA.NRD"\r\n')
time.sleep(1)
drain()

# Upload DER as binary
dy2 = f"~DYE:WEBLINK1_CA,B,NRD,{len(der_data)},,".encode('utf-8') + der_data + b"\n"
out_ep.write(dy2)
time.sleep(3)
drain()

# Verify
out_ep.write(b"^XA^HWE:*.NRD^XZ")
time.sleep(2)
resp = drain()

# === Method 3: Try uploading via SGD setvar with inline PEM ===
print("\n=== Method 3: Try inline PEM via setvar ===")
# Some Link-OS firmware versions support setting cert inline
cmd3 = f'! U1 setvar "weblink.ip.conn1.ca_cert.pem" "{pem_data}"\r\n'
out_ep.write(cmd3.encode('utf-8'))
time.sleep(2)
drain()

# === Method 4: Try ~DY with A (ASCII) type instead of B (binary) ===
print("\n=== Method 4: ~DY with A type ===")
# Delete first
out_ep.write(b'! U1 do "file.delete" "E:WEBLINK1_CA.NRD"\r\n')
time.sleep(1)
drain()

dy4 = f"~DYE:WEBLINK1_CA,A,NRD,{len(pem_bytes)},,{pem_data}\n"
out_ep.write(dy4.encode('utf-8'))
time.sleep(3)
drain()

out_ep.write(b"^XA^HWE:*.NRD^XZ")
time.sleep(2)
drain()

# === Method 5: Try with the full filename including .NRD extension ===
print("\n=== Method 5: Filename with .NRD extension ===")
out_ep.write(b'! U1 do "file.delete" "E:WEBLINK1_CA.NRD"\r\n')
time.sleep(1)
drain()

dy5 = f"~DYE:WEBLINK1_CA.NRD,A,NRD,{len(pem_bytes)},,{pem_data}\n"
out_ep.write(dy5.encode('utf-8'))
time.sleep(3)
drain()

out_ep.write(b"^XA^HWE:*.NRD^XZ")
time.sleep(2)
drain()

# === Final: Put back working PEM upload and reset ===
print("\n=== Restoring PEM cert with original syntax and resetting ===")
out_ep.write(b'! U1 do "file.delete" "E:WEBLINK1_CA.NRD"\r\n')
time.sleep(1)
dy_final = f"~DYE:WEBLINK1_CA,B,NRD,{len(pem_bytes)},,{pem_data}\n"
out_ep.write(dy_final.encode('utf-8'))
time.sleep(2)
drain()

# Check all NRD files one more time
print("\n=== Final file listing ===")
out_ep.write(b"^XA^HWE:*.NRD^XZ")
time.sleep(2)
drain()

# Now also try: put the full chain (server cert + CA) on server side
# AND have the CA on the printer. The printer might need both.
print("\nDone. NOT resetting yet - check results first.")
