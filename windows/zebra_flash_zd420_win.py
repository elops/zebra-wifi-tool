#!/usr/bin/env python3
"""
Flash ZD420 firmware to V84.20.23Z via raw USB (Windows).

Firmware is bundled inside the exe. On first run, a one-time UAC prompt +
WinUSB driver bind happens, then the flash proceeds.
"""

import os
import sys
import time
import zipfile

import _zebrausb as zu

PRODUCT_ID = 0x0120
FIRMWARE_ZIP_NAME = "V84.20.23Z.zip"
FIRMWARE_ZPL_NAME = "V84.20.23Z.zpl"
TARGET_VERSION_PREFIX = "V84"


def main():
    if sys.platform != "win32":
        sys.stderr.write("This build is Windows-only.\n")
        sys.exit(1)

    backend = zu.load_backend()
    dev = zu.ensure_printer_ready(backend, product_id=PRODUCT_ID, product_name="ZD420")
    if dev is None:
        zu.pause_and_exit(1)

    zu.detach_if_needed(dev)
    out_ep, in_ep = zu.get_endpoints(dev)

    current_fw = "unknown"
    try:
        try:
            while True:
                in_ep.read(8192, timeout=500)
        except Exception:
            pass
        out_ep.write(b'! U1 getvar "appl.name"\r\n')
        time.sleep(1)
        response = in_ep.read(4096, timeout=3000)
        current_fw = bytes(response).decode("utf-8", errors="ignore").strip().strip('"')
        print("Current firmware: {}".format(current_fw))
        if current_fw.startswith(TARGET_VERSION_PREFIX):
            print("Printer is already on {} firmware ({}). No upgrade needed.".format(
                TARGET_VERSION_PREFIX, current_fw))
            zu.pause_and_exit(0)
    except Exception:
        print("WARNING: Could not read firmware version, proceeding anyway...")

    firmware_zip = zu.resource_path(FIRMWARE_ZIP_NAME)
    if not os.path.exists(firmware_zip):
        sys.stderr.write("Firmware zip not bundled at {}\n".format(firmware_zip))
        zu.pause_and_exit(1)

    print("Extracting {} from bundled firmware archive...".format(FIRMWARE_ZPL_NAME))
    with zipfile.ZipFile(firmware_zip, "r") as zf:
        if FIRMWARE_ZPL_NAME not in zf.namelist():
            sys.stderr.write("{} not found in zip archive.\n".format(FIRMWARE_ZPL_NAME))
            zu.pause_and_exit(1)
        firmware_data = zf.read(FIRMWARE_ZPL_NAME)

    firmware_size = len(firmware_data)
    print("Firmware size: {} bytes ({:.1f} MB)".format(firmware_size, firmware_size / 1024 / 1024))

    print("\nThis will upgrade the ZD420 from {} to V84.20.23Z.".format(current_fw))
    try:
        confirm = input("Proceed? [y/N]: ")
    except EOFError:
        confirm = ""
    if confirm.strip().lower() != "y":
        print("Aborted.")
        zu.pause_and_exit(0)

    CHUNK_SIZE = 8192
    WRITE_TIMEOUT = 30000
    total_chunks = (firmware_size + CHUNK_SIZE - 1) // CHUNK_SIZE
    sent = 0
    last_pct = -1

    print("Sending firmware ({} chunks)... this will take a few minutes.".format(total_chunks))
    try:
        import usb.core as _uc
        for i in range(0, firmware_size, CHUNK_SIZE):
            chunk = firmware_data[i:i + CHUNK_SIZE]
            out_ep.write(chunk, timeout=WRITE_TIMEOUT)
            sent += len(chunk)
            pct = int(sent * 100 / firmware_size)
            if pct >= last_pct + 10:
                print("  {}% ({}/{})".format(pct, sent, firmware_size))
                last_pct = pct
        print("  100% -- all data sent.")
    except _uc.USBError as e:
        if sent > firmware_size * 0.9:
            print("\n  USB connection closed at {:.0f}% ({})".format(sent * 100 / firmware_size, e))
            print("  Printer is likely flashing firmware.")
        else:
            sys.stderr.write("\nERROR: Transfer failed at {:.0f}% ({})\n".format(
                sent * 100 / firmware_size, e))
            zu.pause_and_exit(1)

    print(
        "\nFirmware sent. The printer is now flashing and will reboot.\n"
        "This process takes 2-3 minutes. Do NOT power off the printer.\n\n"
        "After reboot, run this exe again to verify V84 is installed,\n"
        "then run zebra_wifi_setup.exe to provision.\n"
    )
    zu.pause_and_exit(0)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
    except Exception as e:
        sys.stderr.write("\nERROR: {}\n".format(e))
        zu.pause_and_exit(1)
