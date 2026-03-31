#!/usr/bin/env python3
"""
Unified Zebra WiFi + Weblink + CA Certificate provisioning tool.
Supports ZD420 (firmware V84+) and ZD421 printers.
"""

import usb.core
import os
import sys
import binascii
import traceback
import time
from passlib.utils import pbkdf2

VENDOR_ID = 0x0a5f

SUPPORTED_PRINTERS = {
    0x0120: "ZD420",
    0x0185: "ZD421",
}

if os.geteuid() != 0:
    sys.stderr.write("pyusb this tool depends on requires root privileges, please run as root. Exiting...\n")
    sys.exit(1)

# Auto-detect printer model
device = None
model_name = None

for product_id, name in SUPPORTED_PRINTERS.items():
    device = usb.core.find(idVendor=VENDOR_ID, idProduct=product_id)
    if device is not None:
        model_name = name
        print(f"Detected {name} printer (USB product ID: {hex(product_id)})")
        break

if device is None:
    sys.stderr.write("Could not find a supported Zebra printer (ZD420/ZD421) attached. Exiting...\n")
    sys.exit(1)

# Check firmware version for ZD420
if model_name == "ZD420":
    if device.is_kernel_driver_active(0):
        device.detach_kernel_driver(0)
    try:
        cfg = device.get_active_configuration()
        iface = cfg[(0, 0)]
        out_ep = iface[0]
        in_ep = iface[1]
        out_ep.write(b'! U1 getvar "appl.name"\r\n')
        time.sleep(1)
        resp = in_ep.read(4096, timeout=3000)
        fw = bytes(resp).decode('utf-8', errors='ignore').strip().strip('"')
        print(f"Firmware version: {fw}")
        if fw.startswith("V77") or fw.startswith("V78") or fw.startswith("V79"):
            sys.stderr.write(f"\nERROR: ZD420 firmware {fw} does not support custom CA certificates.\n")
            sys.stderr.write("Upgrade to V84.20.23Z or later. See FIRMWARE_UPGRADE.md for instructions.\n")
            sys.exit(1)
    except usb.core.USBTimeoutError:
        print("WARNING: Could not read firmware version, proceeding anyway...")
    # Re-attach for clean state below
    device = usb.core.find(idVendor=VENDOR_ID, idProduct=device.idProduct)

SSID = input("Enter WiFi SSID : ")
if not len(SSID):
    sys.stderr.write("Must provide WiFi SSID. Exiting...\n")
    sys.exit(1)

WPA_SECRET = input("Enter WiFi secret : ")
if not len(WPA_SECRET):
    sys.stderr.write("Must provide WiFi secret. Exiting...\n")
    sys.exit(1)

WEBLINK1_URL = input("Enter Weblink1 URL : ")
if not len(WEBLINK1_URL):
    sys.stderr.write("Must provide Weblink1 URL. Exiting...\n")
    sys.exit(1)

DEVICE_LOCATION = input("Enter device location : ")
if not len(DEVICE_LOCATION):
    DEVICE_LOCATION = "Default Location"

# Prompt for the certificate
CERT_PATH = input("Enter path to CA cert file (e.g., ca.pem) [Leave blank to skip]: ")
cert_payload = b""

if CERT_PATH:
    if os.path.exists(CERT_PATH):
        with open(CERT_PATH, "r") as f:
            cert_data = f.read()
        cert_size = len(cert_data.encode('utf-8'))
        dy_command = f"~DYE:WEBLINK1_CA,B,NRD,{cert_size},,{cert_data}\n"
        cert_payload = dy_command.encode('utf-8')
    else:
        sys.stderr.write(f"Certificate file not found at {CERT_PATH}. Exiting...\n")
        sys.exit(1)

# https://github.com/julianofischer/python-wpa-psk-rawkey-gen
WPA_PSK_KEY = pbkdf2.pbkdf2(str.encode(WPA_SECRET), str.encode(SSID), 4096, 32)
WPA_PSK_RAWKEY = binascii.hexlify(WPA_PSK_KEY).decode("utf-8").upper()

# ZD421 needs zebra_connector disabled; ZD420 does not have this setting
zebra_connector_cmd = ""
if model_name == "ZD421":
    zebra_connector_cmd = '! U1 setvar "weblink.zebra_connector.enable" "off"'

CONFIG_CMD = """
^XA
^WIA
^NC2
^NPP
^KC0,0,,
^WAD,D
^WEOFF,1,O,H,,,,
^WP0,0
^WR,,,,100
^WS{ssid},I,L,,,
^NBS
^WLOFF,,
^WKOFF,,,,
^WX09,{psk}
^XZ
^XA
^JUS
^XZ
! U1 setvar "media.type" "journal"
! U1 setvar "media.speed" "6.0"
! U1 setvar "media.thermal_mode" "DT"
! U1 setvar "ezpl.print_width" "609"
! U1 setvar "ezpl.print_method" "direct thermal"
! U1 setvar "alerts.configured" "SGD SET,SDK,Y,N,WEBLINK.IP.CONN1,0,N,capture.channel1.data.raw|ALL MESSAGES,SDK,Y,Y,WEBLINK.IP.CONN1,0,N,"
! U1 setvar "capture.channel1.delimiter" "\\\\\\\\015\\\\\\\\012"
! U1 setvar "capture.channel1.max_length" "10"
! U1 setvar "capture.channel1.port" "bt"
! U1 setvar "weblink.ip.conn1.location" "{url}"
{zebra_connector}
! U1 setvar "device.location" "{location}"
! U1 setvar "device.friendly_name" "{model}"
""".format(
    ssid=SSID,
    psk=WPA_PSK_RAWKEY,
    url=WEBLINK1_URL,
    zebra_connector=zebra_connector_cmd,
    location=DEVICE_LOCATION,
    model=model_name,
)

if device.is_kernel_driver_active(0):
    print("Detaching kernel driver...")
    device.detach_kernel_driver(0)

try:
    configuration = device.get_active_configuration()
except:
    print("Exception in user code:")
    print('-' * 60)
    traceback.print_exc(file=sys.stdout)
    print('-' * 60)
    sys.exit(1)

interface = configuration[(0, 0)]
out_endpoint = interface[0]
in_endpoint = interface[1]

try:
    # 1. Send configuration and certificate payload
    print(f"Sending configuration to {model_name}...")
    initial_payload = CONFIG_CMD.encode('utf-8')
    if cert_payload:
        print("Including CA certificate...")
        initial_payload += cert_payload

    out_endpoint.write(initial_payload)

    # 2. Verify certificate if one was uploaded
    if cert_payload:
        print("Waiting 2 seconds for the printer to process the certificate...")
        time.sleep(2)

        print("Verifying certificate on the printer...")
        out_endpoint.write(b'! U1 getvar "file.dir"\r\n')

        try:
            response = in_endpoint.read(8192, timeout=5000)
            response_text = bytes(response).decode('utf-8', errors='ignore')

            if "WEBLINK1_CA.NRD" in response_text:
                print("SUCCESS: WEBLINK1_CA.NRD found on the printer's drive.")
            else:
                print("WARNING: WEBLINK1_CA.NRD was not found in the directory listing.")
                print(f"Printer response: {response_text.strip()}")
        except usb.core.USBTimeoutError:
            print("WARNING: Timed out waiting for verification response from the printer.")

    # 3. Trigger the reboot
    print("Sending reset command to reboot the device...")
    reset_command = b'\n! U1 setvar "device.reset" "true"\n'
    out_endpoint.write(reset_command)

    print(f"{model_name} provisioning completed. Printer is rebooting.")

except Exception as e:
    sys.stderr.write("Error occurred while trying to configure printer, exiting...\n")
    sys.stderr.write("{}\n".format(e))
    sys.exit(1)
