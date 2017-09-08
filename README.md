# Zebra wifi configurator 
Small tool to configure Zebra ZD420 printer to connect to some WPA-PSK protected WiFi network

## Notes
* Tool requires root privileges due to how pyusb works
* After tool is ran printer needs to be rebooted manually to apply the changes.
* Tool currently supports only WPA/PSK security type WiFi networks,
  For other types of WiFi security WX09 part in CONNECT_CFG would need to be
  adjusted along with respective key hashing algorithm for given security type

