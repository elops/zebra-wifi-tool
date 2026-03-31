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

# Drain any pending data
try:
    while True:
        in_ep.read(8192, timeout=500)
except:
    pass

queries = [
    "ssl.peer_verify.enable",
    "ssl.self_signed_cert.enable",
    "weblink.ip.conn1.ssl.peer_verify",
    "weblink.ip.conn1.ssl.self_signed_cert",
    "ip.conn1.ssl.peer_verify",
    "ssl.peer_verify",
    "ssl.self_signed",
    "weblink.ip.conn1.ca_certificates",
    "weblink.ip.conn1.ca_certificate",
    "weblink.ip.conn1.certificate",
    "device.firmware",
    "appl.name",
]

for var in queries:
    cmd = f'! U1 getvar "{var}"\r\n'
    out_ep.write(cmd.encode('utf-8'))
    time.sleep(1)
    try:
        response = in_ep.read(4096, timeout=3000)
        text = bytes(response).decode('utf-8', errors='ignore').strip()
        print(f"{var} = {text}")
    except usb.core.USBTimeoutError:
        print(f"{var} = <timeout>")
