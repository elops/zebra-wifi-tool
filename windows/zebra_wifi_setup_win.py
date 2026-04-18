#!/usr/bin/env python3
"""
Zebra WiFi + Weblink + CA Certificate provisioning (Windows).

Supports ZD420 (firmware V84+) and ZD421 printers. The CA certificate
(rootCA.crt) is bundled into this exe; all other options are prompted.
"""

import binascii
import os
import sys
import time
import traceback

import _zebrausb as zu

from passlib.utils import pbkdf2

SUPPORTED_PRINTERS = {
    0x0120: "ZD420",
    0x0185: "ZD421",
}

BUSY_RETRIES = 5
BUSY_RETRY_DELAY = 2
BUNDLED_CA_CERT = "rootCA.crt"


def is_busy_error(exc):
    if getattr(exc, "errno", None) == 16:
        return True
    return "Resource busy" in str(exc) or "[Errno 16]" in str(exc)


def usb_write_retry(endpoint, payload, description):
    import usb.core as _uc
    for attempt in range(1, BUSY_RETRIES + 1):
        try:
            endpoint.write(payload)
            return
        except _uc.USBError as exc:
            if not is_busy_error(exc) or attempt == BUSY_RETRIES:
                raise
            print("Resource busy while {} (attempt {}/{}), retrying in {}s...".format(
                description, attempt, BUSY_RETRIES, BUSY_RETRY_DELAY))
            time.sleep(BUSY_RETRY_DELAY)


def detect_printer(backend):
    """Find a supported printer; install WinUSB driver one-time if needed."""
    for pid, name in SUPPORTED_PRINTERS.items():
        dev = zu.find_printer(backend, product_id=pid)
        if dev is not None and zu._probe_usable(dev):
            print("Detected {} printer (USB product ID: {}).".format(name, hex(pid)))
            return dev, name

    # Not usable via libusb — either not plugged in, or WinUSB isn't bound yet.
    pid = zu.find_zebra_pid_via_pnp()
    if pid is None or pid not in SUPPORTED_PRINTERS:
        sys.stderr.write("No supported Zebra printer (ZD420/ZD421) found on USB.\n")
        return None, None

    name = SUPPORTED_PRINTERS[pid]
    print("Found {} at VID=0x0A5F PID=0x{:04X} but libusb cannot access it.".format(name, pid))
    print("WinUSB driver needs to be installed (one-time).")
    if not zu.is_admin():
        print("Requesting administrator rights...")
        if not zu.elevate_self():
            sys.stderr.write("Elevation denied.\n")
            return None, None
        sys.exit(0)
    if not zu.install_winusb_driver(pid):
        return None, None
    for _ in range(10):
        dev = zu.find_printer(backend, product_id=pid)
        if dev is not None and zu._probe_usable(dev):
            return dev, name
        time.sleep(1)
    sys.stderr.write("Printer still not accessible after driver install.\n")
    return None, None


def main():
    if sys.platform != "win32":
        sys.stderr.write("This build is Windows-only.\n")
        sys.exit(1)

    backend = zu.load_backend()
    dev, model_name = detect_printer(backend)
    if dev is None:
        zu.pause_and_exit(1)

    zu.detach_if_needed(dev)
    try:
        out_ep, in_ep = zu.get_endpoints(dev)
    except Exception:
        print("Exception getting endpoints:")
        print("-" * 60)
        traceback.print_exc(file=sys.stdout)
        print("-" * 60)
        zu.pause_and_exit(1)

    if model_name == "ZD420":
        try:
            out_ep.write(b'! U1 getvar "appl.name"\r\n')
            time.sleep(1)
            resp = in_ep.read(4096, timeout=3000)
            fw = bytes(resp).decode("utf-8", errors="ignore").strip().strip('"')
            print("Firmware version: {}".format(fw))
            if fw.startswith("V77") or fw.startswith("V78") or fw.startswith("V79"):
                sys.stderr.write(
                    "\nERROR: ZD420 firmware {} does not support custom CA certificates.\n"
                    "Upgrade using zebra_flash_zd420.exe first.\n".format(fw)
                )
                zu.pause_and_exit(1)
        except Exception:
            print("WARNING: Could not read firmware version, proceeding anyway...")

    SSID = input("Enter WiFi SSID : ")
    if not SSID:
        sys.stderr.write("Must provide WiFi SSID. Exiting...\n")
        zu.pause_and_exit(1)

    WPA_SECRET = input("Enter WiFi secret : ")
    if not WPA_SECRET:
        sys.stderr.write("Must provide WiFi secret. Exiting...\n")
        zu.pause_and_exit(1)

    WEBLINK1_URL = input("Enter Weblink1 URL : ")
    if not WEBLINK1_URL:
        sys.stderr.write("Must provide Weblink1 URL. Exiting...\n")
        zu.pause_and_exit(1)

    DEVICE_LOCATION = input("Enter device location [Default Location]: ")
    if not DEVICE_LOCATION:
        DEVICE_LOCATION = "Default Location"

    cert_path = zu.resource_path(BUNDLED_CA_CERT)
    if not os.path.exists(cert_path):
        sys.stderr.write("Bundled CA cert missing at {}\n".format(cert_path))
        zu.pause_and_exit(1)
    with open(cert_path, "r", encoding="utf-8") as f:
        cert_data = f.read()
    cert_size = len(cert_data.encode("utf-8"))
    dy_command1 = "~DYE:WEBLINK1_CA,B,NRD,{},,{}\n".format(cert_size, cert_data)
    dy_command2 = "~DYE:WEBLINK2_CA,B,NRD,{},,{}\n".format(cert_size, cert_data)
    cert_payload = (dy_command1 + dy_command2).encode("utf-8")

    WPA_PSK_KEY = pbkdf2.pbkdf2(str.encode(WPA_SECRET), str.encode(SSID), 4096, 32)
    WPA_PSK_RAWKEY = binascii.hexlify(WPA_PSK_KEY).decode("utf-8").upper()

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

    try:
        print("Sending configuration to {}...".format(model_name))
        payload = CONFIG_CMD.encode("utf-8") + cert_payload
        print("Including bundled CA certificate...")
        usb_write_retry(out_ep, payload, "sending configuration")

        print("Waiting 2 seconds for the printer to process the certificate...")
        time.sleep(2)

        print("Verifying certificate on the printer...")
        usb_write_retry(out_ep, b'! U1 getvar "file.dir"\r\n', "querying file.dir")
        try:
            response = in_ep.read(8192, timeout=5000)
            response_text = bytes(response).decode("utf-8", errors="ignore")
            found1 = "WEBLINK1_CA.NRD" in response_text
            found2 = "WEBLINK2_CA.NRD" in response_text
            print("  WEBLINK1_CA.NRD: {}".format("OK" if found1 else "NOT FOUND"))
            print("  WEBLINK2_CA.NRD: {}".format("OK" if found2 else "NOT FOUND"))
            if not (found1 and found2):
                print("Printer response: {}".format(response_text.strip()))
        except Exception:
            print("WARNING: Timed out waiting for verification response from the printer.")

        print("Sending reset command to reboot the device...")
        usb_write_retry(out_ep, b'\n! U1 setvar "device.reset" "true"\n', "sending reset")
        print("{} provisioning completed. Printer is rebooting.".format(model_name))
    except Exception as e:
        sys.stderr.write("Error occurred while trying to configure printer.\n{}\n".format(e))
        zu.pause_and_exit(1)

    zu.pause_and_exit(0)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
    except Exception as e:
        sys.stderr.write("\nERROR: {}\n".format(e))
        zu.pause_and_exit(1)
