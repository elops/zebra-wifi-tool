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

# Drain any pending data
try:
    while True:
        in_ep.read(8192, timeout=500)
except:
    pass

def query(var):
    cmd = f'! U1 getvar "{var}"\r\n'
    out_ep.write(cmd.encode('utf-8'))
    time.sleep(1)
    try:
        response = in_ep.read(8192, timeout=5000)
        text = bytes(response).decode('utf-8', errors='ignore').strip()
        return text
    except usb.core.USBTimeoutError:
        return "<timeout>"

def send(data):
    if isinstance(data, str):
        data = data.encode('utf-8')
    out_ep.write(data)
    time.sleep(1)

def drain():
    try:
        while True:
            resp = in_ep.read(8192, timeout=2000)
            text = bytes(resp).decode('utf-8', errors='ignore').strip()
            if text:
                print(f"  Response: {text[:500]}")
    except:
        pass

# --- Probe all possible cert-related SGD variables ---
print("=== Probing cert-related SGD variables ===")
cert_vars = [
    "weblink.ip.conn1.ca_cert.pem",
    "weblink.ip.conn1.ca_cert",
    "weblink.ip.conn1.ca_certs",
    "weblink.ip.conn1.ca_certificate",
    "weblink.ip.conn1.ca_certificates",
    "weblink.ip.conn1.trust",
    "weblink.ip.conn1.verify",
    "weblink.ip.conn1.peer_verify",
    "weblink.ip.conn1.ssl_peer_verify",
    "ssl.trusted_certs",
    "ssl.ca_cert",
    "ssl.ca_certificate",
    "ssl.ca_certificates",
    "ssl.trust",
    "ssl.trusted",
    "ssl.peer_verify.conn1",
    "ssl.verify",
    "certificate.list",
    "certificate.ca",
    "crypto.ca_cert",
    "ip.ssl.ca_cert",
    "weblink.ssl.ca_cert",
]

for var in cert_vars:
    result = query(var)
    if result != '"?"' and result != '?':
        print(f"  >>> {var} = {result}")
    else:
        print(f"  {var} = ?")

# --- Try alldo/allset to discover weblink variables ---
print("\n=== Probing weblink alldo/allset ===")
for var in ["weblink.ip.conn1", "ssl", "certificate", "crypto"]:
    print(f"\n--- allset {var} ---")
    cmd = f'! U1 getvar "allcv"\r\n'
    # Try listing all variables in category
    cmd2 = f'{{}}{{}}! U1 getvar "{var}"\r\n'

# --- Try DER format upload ---
print("\n=== Trying DER format cert upload ===")
pem_path = "./ssl/rootCA.crt"
der_path = "/tmp/rootCA.der"

# Convert PEM to DER
subprocess.run(["openssl", "x509", "-in", pem_path, "-outform", "DER", "-out", der_path], check=True)

with open(der_path, "rb") as f:
    der_data = f.read()

print(f"DER cert size: {len(der_data)} bytes")

# Try uploading as different file names and formats
uploads = [
    ("E:SSL_CA.NRD", "B", "NRD"),
    ("E:TRUSTED_CERTS.NRD", "B", "NRD"),
    ("E:WEBLINK1_CA.DER", "B", "DER"),
    ("E:CA_CERT.NRD", "B", "NRD"),
]

for filename, btype, ext in uploads:
    print(f"\n  Uploading {filename} ({len(der_data)} bytes DER)...")
    dy_cmd = f"~DY{filename},{btype},{ext},{len(der_data)},,"
    out_ep.write(dy_cmd.encode('utf-8') + der_data + b"\n")
    time.sleep(2)
    drain()

# Also try re-uploading PEM as different names
with open(pem_path, "r") as f:
    pem_data = f.read()
pem_size = len(pem_data.encode('utf-8'))

pem_uploads = [
    "E:WEBLINK1_CA.PEM",
    "E:CA.PEM",
    "E:CONN1_CA.NRD",
]

for filename in pem_uploads:
    print(f"\n  Uploading {filename} ({pem_size} bytes PEM)...")
    dy_cmd = f"~DY{filename},B,NRD,{pem_size},,{pem_data}\n"
    out_ep.write(dy_cmd.encode('utf-8'))
    time.sleep(2)
    drain()

# --- Try SGD do commands to install cert ---
print("\n=== Trying 'do' commands to install/activate cert ===")
do_cmds = [
    '! U1 do "weblink.ip.conn1.ca_cert.install" "E:WEBLINK1_CA.NRD"\r\n',
    '! U1 do "ssl.ca_cert.install" "E:WEBLINK1_CA.NRD"\r\n',
    '! U1 do "certificate.install" "E:WEBLINK1_CA.NRD"\r\n',
    '! U1 do "crypto.install_cert" "E:WEBLINK1_CA.NRD"\r\n',
    '! U1 setvar "ssl.ca_cert" "E:WEBLINK1_CA.NRD"\r\n',
    '! U1 setvar "weblink.ip.conn1.ca_cert" "E:WEBLINK1_CA.NRD"\r\n',
    '! U1 setvar "weblink.ip.conn1.ca_certificate" "E:WEBLINK1_CA.NRD"\r\n',
]

for cmd in do_cmds:
    print(f"  Trying: {cmd.strip()}")
    out_ep.write(cmd.encode('utf-8'))
    time.sleep(1)
    drain()

print("\n=== Done. Checking file listing ===")
send('! U1 getvar "file.dir"\r\n')
time.sleep(1)
drain()
