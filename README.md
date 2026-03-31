# Zebra wifi configurator 
Tool to configure Zebra ZD420/ZD421 printers to connect to a WPA-PSK WiFi
network, set up weblink, and optionally install a custom CA certificate for
HTTPS weblink connections.

## Supported printers

| Model | USB Product ID | Min firmware | Notes |
|-------|---------------|-------------|-------|
| ZD420 | 0x0120 | V84.20.10Z | Older V77.x firmware must be upgraded first, see [FIRMWARE_UPGRADE.md](FIRMWARE_UPGRADE.md) |
| ZD421 | 0x0185 | V77.19.16Z | Works out of the box |

## Usage

```
sudo .venv3/bin/python3 zebra_wifi_setup.py
```

The script auto-detects the printer model and prompts for:
- WiFi SSID
- WiFi WPA-PSK secret
- Weblink URL (e.g. `https://zserver.hallochef.net:8500/`)
- Device location
- Path to CA certificate file (PEM format, optional)

## Scripts

| Script | Description |
|--------|-------------|
| `zebra_wifi_setup.py` | **Unified** provisioning script for ZD420 and ZD421 with cert support |
| `zebra_wifi_setup-zd420.py` | Legacy ZD420 without cert support |
| `zebra_wifi_setup-zd420-with-cert.py` | Legacy ZD420 with cert support |
| `zebra_wifi_setup-zd421.py` | Legacy ZD421 without cert support |
| `zebra_wifi_setup-zd421-with-cert.py` | Legacy ZD421 with cert support |

## ZD420 firmware upgrade

ZD420 printers running firmware V77.x (Link-OS 3) do not support custom CA
certificates. They must be upgraded to V84.20.10Z or later. See
[FIRMWARE_UPGRADE.md](FIRMWARE_UPGRADE.md) for the procedure.

## Notes
* Tool requires root privileges due to how pyusb works
* Tool currently supports only WPA/PSK security type WiFi networks.
  For other types of WiFi security the WX09 part in CONFIG_CMD would need to be
  adjusted along with respective key hashing algorithm for given security type.
  For more info on how to configure other WiFi security types consult
  https://www.zebra.com/content/dam/zebra/manuals/en-us/software/zpl-zbi2-pm-en.pdf
