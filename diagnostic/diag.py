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

queries = [
    "weblink.ip.conn1.location",
    "weblink.ip.conn1.status",
    "weblink.ip.conn1.auth_scheme",
    "weblink.ip.conn1.maximum_simultaneous_connections",
    "weblink.ip.conn1.num_connections",
    "weblink.ip.conn1.retry_interval",
    "weblink.ip.conn1.connection_id_list",
    "weblink.ip.conn1.test.panel_key",
    "ip.addr",
    "ip.gateway",
    "ip.dns_servers",
    "wlan.ip.addr",
    "wlan.status",
    "wlan.ssid",
    "wlan.signal_strength",
    "device.uptime",
    "ssl.revocation.enable",
]

for var in queries:
    cmd = f'! U1 getvar "{var}"\r\n'
    out_ep.write(cmd.encode('utf-8'))
    time.sleep(0.3)
    try:
        response = in_ep.read(4096, timeout=3000)
        text = bytes(response).decode('utf-8', errors='ignore').strip()
        print(f"{var} = {text}")
    except usb.core.USBTimeoutError:
        print(f"{var} = <timeout>")
    except Exception as e:
        print(f"{var} = <error: {e}>")
