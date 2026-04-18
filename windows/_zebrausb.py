"""Shared Windows USB helpers for Zebra provisioning tools.

Handles:
  * Locating the bundled libusb-1.0.dll / wdi-simple.exe / data files.
  * UAC self-elevation when a one-time WinUSB bind is needed.
  * Driver install via wdi-simple.exe on first encounter of the printer.
  * Returning a ready-to-use pyusb Device with endpoints.
"""

import ctypes
import os
import re
import subprocess
import sys
import time

VID = 0x0A5F


def resource_path(rel):
    if getattr(sys, "frozen", False):
        base = sys._MEIPASS
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, rel)


def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False


def elevate_self():
    if getattr(sys, "frozen", False):
        exe = sys.executable
        params = subprocess.list2cmdline(sys.argv[1:])
    else:
        exe = sys.executable
        params = subprocess.list2cmdline([os.path.abspath(sys.argv[0])] + sys.argv[1:])
    rc = ctypes.windll.shell32.ShellExecuteW(None, "runas", exe, params, None, 1)
    return rc > 32


def pause_and_exit(code=0):
    try:
        input("\nPress Enter to exit...")
    except EOFError:
        pass
    sys.exit(code)


def load_backend():
    import usb.backend.libusb1
    dll = resource_path("libusb-1.0.dll")
    if not os.path.exists(dll):
        sys.stderr.write("libusb-1.0.dll missing at {}\n".format(dll))
        sys.exit(1)
    be = usb.backend.libusb1.get_backend(find_library=lambda _: dll)
    if be is None:
        sys.stderr.write("Failed to initialise libusb backend.\n")
        sys.exit(1)
    return be


def find_printer(backend, product_id=None):
    import usb.core
    kwargs = {"idVendor": VID, "backend": backend}
    if product_id is not None:
        kwargs["idProduct"] = product_id
    return usb.core.find(**kwargs)


def find_zebra_pid_via_pnp(want_pid=None):
    """Return the PID of a connected Zebra via Windows PnP (works pre-driver-bind)."""
    try:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "Get-PnpDevice -PresentOnly | "
             "Where-Object { $_.InstanceId -like '*VID_0A5F*' } | "
             "Select-Object -ExpandProperty InstanceId"],
            capture_output=True, text=True, timeout=15,
            creationflags=0x08000000,  # CREATE_NO_WINDOW
        )
        candidates = []
        for line in r.stdout.splitlines():
            m = re.search(r"VID_0A5F&PID_([0-9A-Fa-f]{4})", line)
            if m:
                candidates.append(int(m.group(1), 16))
        if want_pid is not None:
            return want_pid if want_pid in candidates else None
        return candidates[0] if candidates else None
    except Exception as e:
        sys.stderr.write("PnP enumeration failed: {}\n".format(e))
    return None


def install_winusb_driver(pid):
    wdi = resource_path("wdi-simple.exe")
    if not os.path.exists(wdi):
        sys.stderr.write("wdi-simple.exe missing at {}\n".format(wdi))
        return False
    print("Installing WinUSB driver for VID=0x{:04X} PID=0x{:04X}...".format(VID, pid))
    print("If Windows warns about an unverified publisher, choose 'Install this driver anyway'.")
    r = subprocess.run(
        [wdi,
         "--vid", "0x{:04X}".format(VID),
         "--pid", "0x{:04X}".format(pid),
         "--type", "0",
         "--name", "Zebra WinUSB (zebra-wifi-tool)"],
    )
    if r.returncode != 0:
        sys.stderr.write("wdi-simple returned {}\n".format(r.returncode))
        return False
    print("Driver installed. Waiting for Windows to rebind...")
    time.sleep(4)
    return True


def ensure_printer_ready(backend, product_id=None, product_name=None):
    """Locate printer, installing WinUSB driver via UAC if needed. Return pyusb Device or None."""
    dev = find_printer(backend, product_id=product_id)
    if dev is not None:
        return dev

    pid = find_zebra_pid_via_pnp(want_pid=product_id)
    if pid is None:
        want = product_name or "Zebra"
        msg = "No {} USB device (VID 0x0A5F".format(want)
        if product_id is not None:
            msg += " PID 0x{:04X}".format(product_id)
        msg += ") found. Is it plugged in and powered on?\n"
        sys.stderr.write(msg)
        return None

    print("Found Zebra at VID=0x{:04X} PID=0x{:04X} but libusb cannot access it.".format(VID, pid))
    print("WinUSB driver needs to be installed (one-time).")
    if not is_admin():
        print("Requesting administrator rights...")
        if not elevate_self():
            sys.stderr.write("Elevation denied.\n")
            return None
        sys.exit(0)  # elevated child has taken over
    if not install_winusb_driver(pid):
        return None
    for _ in range(10):
        dev = find_printer(backend, product_id=product_id)
        if dev is not None:
            return dev
        time.sleep(1)
    sys.stderr.write("Printer still not accessible after driver install.\n")
    return None


def detach_if_needed(dev):
    try:
        if dev.is_kernel_driver_active(0):
            dev.detach_kernel_driver(0)
    except Exception:
        pass  # no-op on Windows/WinUSB


def get_endpoints(dev):
    cfg = dev.get_active_configuration()
    intf = cfg[(0, 0)]
    return intf[0], intf[1]
