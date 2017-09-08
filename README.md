# Zebra wifi configurator 
Small tool to configure Zebra ZD420 printer to connect to some WPA-PSK protected WiFi network

## Notes
* Tool requires root privileges due to how pyusb works
* Tool currently supports only WPA/PSK security type WiFi networks,
  For other types of WiFi security WX09 part in CONFIG_CMD would need to be
  adjusted along with respective key hashing algorithm for given security type
  For more info on how to configure other WiFi security types consult
  https://www.zebra.com/content/dam/zebra/manuals/en-us/software/zpl-zbi2-pm-en.pdf
