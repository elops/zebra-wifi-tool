#!/usr/bin/env python

import usb.core
import os
import sys
import binascii
import traceback
from passlib.utils import pbkdf2

if os.geteuid() != 0:
	sys.stderr.write("pyusb this tool depends on requires root privileges, please run as root. Exiting...\n")
	sys.exit(1)

VENDOR_ID = 0x0a5f
PRODUCT_ID = 0x0120
INTERFACE_ID = 0x0
SETTING_ID = 0x0
OUT_ENDPOINT_ID = 0
IN_ENDPOINT_ID = 1

device = usb.core.find(idVendor=VENDOR_ID, idProduct=PRODUCT_ID)

if device is None:
	sys.stderr.write("Could not find Zebra printer attached. Exiting...\n")
	sys.exit(1)

SSID = raw_input("Enter WiFi SSID : ")
if not len(SSID):
	sys.stderr.write("Must provide WiFi SSID. Exiting...\n")
	sys.exit(1)

WPA_SECRET = raw_input("Enter WiFi secret : ")
if not len(WPA_SECRET):
	sys.stderr.write("Must provide WiFi secret. Exiting...\n")
	sys.exit(1)

WEBLINK1_URL = raw_input("Enter Weblink1 URL : ")
if not len(WEBLINK1_URL):
	sys.stderr.write("Must provide Weblink1 URL. Exiting...\n")
	sys.exit(1)

# https://github.com/julianofischer/python-wpa-psk-rawkey-gen
WPA_PSK_KEY = pbkdf2.pbkdf2(str.encode(WPA_SECRET), str.encode(SSID), 4096, 32)
WPA_PSK_RAWKEY = binascii.hexlify(WPA_PSK_KEY).decode("utf-8").upper()

# Connect string template from Zebra configuration tool for win
# Official ZPL-ZBI2 Manual
# https://www.zebra.com/content/dam/zebra/manuals/en-us/software/zpl-zbi2-pm-en.pdf

CONNECT_CFG = """
^XA
^WIA
^NC2
^NPP
^KC0,0,,
^WAD,D
^WEOFF,1,O,H,,,,
^WP0,0
^WR,,,,100
^WS{0},I,L,,,
^NBS
^WLOFF,,
^WKOFF,,,,
^WX09,{1}
^XZ
^XA
^JUS
^XZ
""".format(SSID, WPA_PSK_RAWKEY)

device = usb.core.find(idVendor=VENDOR_ID, idProduct=PRODUCT_ID)

if device is None:
	sys.stderr.write("Could not find Zebra printer attached. Exiting...")
	sys.exit(1)

if device.is_kernel_driver_active(INTERFACE_ID):
	print "Detaching kernel driver..."
	device.detach_kernel_driver(INTERFACE_ID) 

try:
    configuration = device.get_active_configuration()
except:
    print "Exception in user code:"
    print '-'*60
    traceback.print_exc(file=sys.stdout)
    print '-'*60
    sys.exit(1)

# Some ideas and navigation tips from
# https://gist.github.com/mvidner/04ffe0bbea0fc24182772a196f238918
interface = configuration[(INTERFACE_ID, SETTING_ID)]

out_endpoint = interface[OUT_ENDPOINT_ID]
in_endpoint = interface[IN_ENDPOINT_ID]

try:
	out_endpoint.write(CONNECT_CFG)
	print("Printer configured with : \n{}".format(CONNECT_CFG))
except:
	sys.stderr.write("Error occurred while trying to configure printer, exiting...\n")
	sys.exit(1)
