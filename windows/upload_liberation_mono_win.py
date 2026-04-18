#!/usr/bin/env python3
"""
Upload Liberation Mono TTFs to a Zebra printer's E: drive via raw USB (Windows).

Usage:
    upload_liberation_mono.exe           # idempotent upload + verify
    upload_liberation_mono.exe --test    # + print a fixed-width test label
    upload_liberation_mono.exe --force   # re-upload unconditionally
"""

import os
import re
import sys
import time

import _zebrausb as zu


DRIVE = "E"
CHUNK = 16384

FONTS = [
    ("LiberationMono-Regular.ttf",    "LMONO.TTF"),
    ("LiberationMono-Bold.ttf",       "LMONOB.TTF"),
    ("LiberationMono-Italic.ttf",     "LMONOI.TTF"),
    ("LiberationMono-BoldItalic.ttf", "LMONOBI.TTF"),
]


def main():
    if sys.platform != "win32":
        sys.stderr.write("This build is Windows-only.\n")
        sys.exit(1)

    force = "--force" in sys.argv
    test = "--test" in sys.argv

    backend = zu.load_backend()
    dev = zu.ensure_printer_ready(backend)
    if dev is None:
        zu.pause_and_exit(1)

    zu.detach_if_needed(dev)
    out_ep, in_ep = zu.get_endpoints(dev)

    def drain():
        try:
            while True:
                in_ep.read(65536, timeout=300)
        except Exception:
            pass

    def read_quiet(idle_timeout=1500, max_idle=3):
        import usb.core as _uc
        buf = b""
        idle = 0
        while idle < max_idle:
            try:
                r = in_ep.read(65536, timeout=idle_timeout)
                if r:
                    buf += bytes(r)
                    idle = 0
                else:
                    idle += 1
            except _uc.USBError:
                idle += 1
        return buf

    def write_chunked(data):
        off = 0
        while off < len(data):
            n = out_ep.write(data[off:off + CHUNK])
            off += (n if isinstance(n, int) and n > 0 else len(data[off:off + CHUNK]))

    drain()
    out_ep.write(b'! U1 getvar "device.unique_id"\r\n')
    time.sleep(0.3)
    serial = read_quiet(idle_timeout=800, max_idle=2).decode("latin-1", errors="ignore").strip().strip('"')
    print("Printer: " + (serial or "unknown"))

    line_re = re.compile(r"\*\s+([A-Z]):([A-Z0-9_.\-]+)\.TTF\s+(\d+)", re.IGNORECASE)

    def list_ttfs():
        drain()
        out_ep.write("^XA^HW{}:*.TTF^XZ".format(DRIVE).encode())
        time.sleep(0.5)
        text = read_quiet(idle_timeout=1500, max_idle=3).decode("latin-1", errors="ignore")
        return {m.group(2).upper() + ".TTF": int(m.group(3)) for m in line_re.finditer(text)}

    print("\nChecking {}: drive...".format(DRIVE))
    on_printer = list_ttfs()
    if on_printer:
        for name, size in sorted(on_printer.items()):
            print("  already present: {}:{} ({} bytes)".format(DRIVE, name, size))
    else:
        print("  no TTFs on {}: drive".format(DRIVE))

    print("\nUploading Liberation Mono to {}: drive{}...".format(
        DRIVE, " (forced)" if force else ""))
    uploaded = 0
    skipped = 0
    fonts_dir = zu.resource_path("fonts")
    for src_name, dst_name in FONTS:
        src_path = os.path.join(fonts_dir, src_name)
        if not os.path.exists(src_path):
            print("  SKIP {} (not bundled)".format(src_name))
            continue

        host_size = os.path.getsize(src_path)
        remote_size = on_printer.get(dst_name.upper())

        if not force and remote_size == host_size:
            print("  skip {}:{}  (already present, {} bytes)".format(DRIVE, dst_name, host_size))
            skipped += 1
            continue
        if not force and remote_size is not None and remote_size != host_size:
            print("  replace {}:{}  (on-printer={} vs host={})".format(
                DRIVE, dst_name, remote_size, host_size))

        with open(src_path, "rb") as f:
            data = f.read()
        obj = dst_name.rsplit(".", 1)[0]
        header = "~DY{}:{},B,T,{},0,".format(DRIVE, obj, host_size).encode("latin-1")

        drain()
        out_ep.write(header)
        t0 = time.time()
        write_chunked(data)
        out_ep.write(b"\r\n")
        time.sleep(0.8)
        print("  uploaded {} -> {}:{}  ({} bytes in {:.1f}s)".format(
            src_name, DRIVE, dst_name, host_size, time.time() - t0))
        uploaded += 1

    print("\nSummary: uploaded={}, skipped={}".format(uploaded, skipped))

    print("\nVerifying...")
    on_printer = list_ttfs()
    for _src, dst in FONTS:
        src_path = os.path.join(fonts_dir, _src)
        host_size = os.path.getsize(src_path) if os.path.exists(src_path) else None
        remote = on_printer.get(dst.upper())
        if remote is None:
            print("  {}: MISSING".format(dst))
        elif host_size and remote != host_size:
            print("  {}: size mismatch on={} host={}".format(dst, remote, host_size))
        else:
            print("  {}: OK ({} bytes)".format(dst, remote))

    if test:
        print("\nPrinting test label (fixed-width verification)...")
        zpl = (
            "^XA^CI28^LH0,0"
            "^FO20,20^A@N,30,30,E:LMONO.TTF^FD0123456789^FS"
            "^FO20,60^A@N,30,30,E:LMONO.TTF^FDABCDEFGHIJ^FS"
            "^FO20,100^A@N,30,30,E:LMONO.TTF^FDiiiiiiiiii^FS"
            "^FO20,140^A@N,30,30,E:LMONO.TTF^FDWWWWWWWWWW^FS"
            "^FO20,180^A@N,30,30,E:LMONO.TTF^FD\u010c\u0106\u017d\u0160\u0110\u010d\u0107\u017e\u0161\u0111^FS"
            "^FO20,230^A@N,30,30,E:LMONOB.TTF^FDBold \u010c\u0106\u017d\u0160^FS"
            "^FO20,270^A@N,30,30,E:LMONOI.TTF^FDItal \u010c\u0106\u017d\u0160^FS"
            "^FO20,310^A@N,30,30,E:LMONOBI.TTF^FDBoIt \u010c\u0106\u017d\u0160^FS"
            "^FO20,360^A@N,22,22,E:LMONO.TTF^FDPrinter: " + (serial or "?") + "^FS"
            "^XZ"
        )
        out_ep.write(zpl.encode("utf-8"))
        time.sleep(0.5)

    print("\nDone.")
    print("Use in ZPL:  ^FO50,50^A@N,40,40,E:LMONO.TTF^FDHello^FS")
    zu.pause_and_exit(0)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
    except Exception as e:
        sys.stderr.write("\nERROR: {}\n".format(e))
        zu.pause_and_exit(1)
