# ZD420 Firmware Upgrade Procedure

ZD420 printers with firmware V77.x (Link-OS 3) do not support custom CA
certificates for weblink HTTPS connections. The `WEBLINK1_CA.NRD` file is
stored on the printer but ignored by the SSL engine.

Custom CA certificate support was added in firmware **V84.20.10Z** (Link-OS 5,
January 2018). The latest available firmware for the ZD420 is **V84.20.23Z**
(Link-OS 6.4, September 2021).

## Check current firmware version

Connect the printer via USB and run:

```
sudo .venv3/bin/python3 -c "
import usb.core, time
dev = usb.core.find(idVendor=0x0a5f, idProduct=0x0120)
if dev is None: print('ZD420 not found'); exit(1)
if dev.is_kernel_driver_active(0): dev.detach_kernel_driver(0)
cfg = dev.get_active_configuration()
out_ep = cfg[(0,0)][0]; in_ep = cfg[(0,0)][1]
out_ep.write(b'! U1 getvar \"appl.name\"\r\n')
time.sleep(1)
r = in_ep.read(4096, timeout=3000)
print('Firmware:', bytes(r).decode('utf-8', errors='ignore').strip())
"
```

If the version starts with `V77`, `V78`, or `V79` the printer needs upgrading.

## Download firmware

1. Go to the Zebra ZD420 Direct Thermal support page:
   https://www.zebra.com/us/en/support-downloads/printers/desktop/zd420d.html
2. Navigate to the **Downloads** tab
3. Download the latest ZPL firmware (V84.20.23Z.zip)
4. Extract the `.zpl` file from the zip

## Upload firmware via FTP

The printer must be connected to the network (WiFi or USB-to-network) with an
IP address. The firmware file is ~29 MB and the printer's FTP server accepts it
directly.

**Important:** `ip.ftp.execute_file` must be set to `"on"` (the default) so the
printer processes the firmware file rather than just storing it.

```bash
# Extract firmware
unzip V84.20.23Z.zip V84.20.23Z.zpl -d /tmp/

# Upload via FTP (anonymous login, no password)
python3 -c "
from ftplib import FTP
ftp = FTP('PRINTER_IP_ADDRESS')
ftp.login()
with open('/tmp/V84.20.23Z.zpl', 'rb') as f:
    ftp.storbinary('STOR V84.20.23Z.zpl', f, blocksize=8192)
"
```

The FTP connection will drop with an `EOFError` -- this is expected. The printer
begins flashing immediately upon receiving the firmware and reboots itself.

The upgrade takes 2-3 minutes. The printer will reboot automatically when done.

## Alternative: upload via USB

If the printer is not on the network, send the firmware file over the USB
endpoint:

```bash
sudo .venv3/bin/python3 -c "
import usb.core
dev = usb.core.find(idVendor=0x0a5f, idProduct=0x0120)
if dev.is_kernel_driver_active(0): dev.detach_kernel_driver(0)
cfg = dev.get_active_configuration()
out_ep = cfg[(0,0)][0]
with open('/tmp/V84.20.23Z.zpl', 'rb') as f:
    data = f.read()
# Send in chunks
chunk = 4096
for i in range(0, len(data), chunk):
    out_ep.write(data[i:i+chunk])
print('Firmware sent, printer will reboot.')
"
```

## Verify upgrade

After the printer reboots, verify the firmware version using the check command
above. It should report `V84.20.23Z`.

## After upgrade

Run the unified provisioning script to configure WiFi, weblink, and CA
certificate:

```
sudo .venv3/bin/python3 zebra_wifi_setup.py
```

The script auto-detects ZD420/ZD421 and will refuse to proceed on ZD420
printers still running old V77.x firmware.
