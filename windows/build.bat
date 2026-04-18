@echo off
REM ======================================================================
REM  Build the three Windows executables (self-contained):
REM    upload_liberation_mono.exe
REM    zebra_flash_zd420.exe
REM    zebra_wifi_setup.exe
REM
REM  Before running, drop these files into this folder:
REM    libusb-1.0.dll     ->  https://libusb.info/  (64-bit)
REM    wdi-simple.exe     ->  built from https://github.com/pbatard/libwdi
REM  And into the fonts\ subfolder:
REM    LiberationMono-{Regular,Bold,Italic,BoldItalic}.ttf
REM  And into the data\ subfolder:
REM    V84.20.23Z.zip     (copied from ..\firmware\)
REM    rootCA.crt         (copied from ..\ssl\)
REM
REM  Prerequisites:
REM    Python 3.10+ on PATH  (64-bit, matching libusb-1.0.dll)
REM
REM  Output: dist\*.exe
REM ======================================================================

setlocal
cd /d "%~dp0"

where python >nul 2>&1
if errorlevel 1 (
    echo ERROR: python not found on PATH.
    exit /b 1
)

for %%F in (libusb-1.0.dll wdi-simple.exe _zebrausb.py upload_liberation_mono_win.py zebra_flash_zd420_win.py zebra_wifi_setup_win.py) do (
    if not exist "%%F" (echo ERROR: missing %%F & exit /b 1)
)
for %%F in (LiberationMono-Regular.ttf LiberationMono-Bold.ttf LiberationMono-Italic.ttf LiberationMono-BoldItalic.ttf) do (
    if not exist "fonts\%%F" (echo ERROR: missing fonts\%%F & exit /b 1)
)
for %%F in (V84.20.23Z.zip rootCA.crt) do (
    if not exist "data\%%F" (echo ERROR: missing data\%%F & exit /b 1)
)

python -m pip install --quiet --upgrade pyusb pyinstaller passlib
if errorlevel 1 (echo ERROR: pip install failed. & exit /b 1)

echo.
echo === Building upload_liberation_mono.exe ===
python -m PyInstaller --noconfirm --onefile ^
    --name upload_liberation_mono ^
    --add-binary "libusb-1.0.dll;." ^
    --add-binary "wdi-simple.exe;." ^
    --add-data "_zebrausb.py;." ^
    --add-data "fonts\LiberationMono-Regular.ttf;fonts" ^
    --add-data "fonts\LiberationMono-Bold.ttf;fonts" ^
    --add-data "fonts\LiberationMono-Italic.ttf;fonts" ^
    --add-data "fonts\LiberationMono-BoldItalic.ttf;fonts" ^
    upload_liberation_mono_win.py
if errorlevel 1 (echo ERROR: PyInstaller failed for upload_liberation_mono. & exit /b 1)

echo.
echo === Building zebra_flash_zd420.exe ===
python -m PyInstaller --noconfirm --onefile ^
    --name zebra_flash_zd420 ^
    --add-binary "libusb-1.0.dll;." ^
    --add-binary "wdi-simple.exe;." ^
    --add-data "_zebrausb.py;." ^
    --add-data "data\V84.20.23Z.zip;." ^
    zebra_flash_zd420_win.py
if errorlevel 1 (echo ERROR: PyInstaller failed for zebra_flash_zd420. & exit /b 1)

echo.
echo === Building zebra_wifi_setup.exe ===
python -m PyInstaller --noconfirm --onefile ^
    --name zebra_wifi_setup ^
    --add-binary "libusb-1.0.dll;." ^
    --add-binary "wdi-simple.exe;." ^
    --add-data "_zebrausb.py;." ^
    --add-data "data\rootCA.crt;." ^
    zebra_wifi_setup_win.py
if errorlevel 1 (echo ERROR: PyInstaller failed for zebra_wifi_setup. & exit /b 1)

echo.
echo Built:
dir /b dist\*.exe
endlocal
