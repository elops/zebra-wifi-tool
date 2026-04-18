@echo off
REM ======================================================================
REM  Build upload_liberation_mono.exe (self-contained Windows executable)
REM
REM  Before running, drop these files into this folder:
REM    libusb-1.0.dll     ->  https://libusb.info/  (MinGW64 build, 64-bit)
REM    wdi-simple.exe     ->  https://github.com/pbatard/libwdi/releases
REM                            (use the 64-bit build)
REM  And into the fonts\ subfolder:
REM    LiberationMono-Regular.ttf
REM    LiberationMono-Bold.ttf
REM    LiberationMono-Italic.ttf
REM    LiberationMono-BoldItalic.ttf
REM       ->  https://github.com/liberationfonts/liberation-fonts/releases
REM
REM  Prerequisites:
REM    Python 3.10+ on PATH  (64-bit, matching libusb-1.0.dll)
REM
REM  Output:
REM    dist\upload_liberation_mono.exe
REM ======================================================================

setlocal
cd /d "%~dp0"

where python >nul 2>&1
if errorlevel 1 (
    echo ERROR: python not found on PATH.
    exit /b 1
)

for %%F in (libusb-1.0.dll wdi-simple.exe upload_liberation_mono_win.py) do (
    if not exist "%%F" (
        echo ERROR: missing %%F in %~dp0
        exit /b 1
    )
)
for %%F in (LiberationMono-Regular.ttf LiberationMono-Bold.ttf LiberationMono-Italic.ttf LiberationMono-BoldItalic.ttf) do (
    if not exist "fonts\%%F" (
        echo ERROR: missing fonts\%%F
        exit /b 1
    )
)

python -m pip install --quiet --upgrade pyusb pyinstaller
if errorlevel 1 (
    echo ERROR: pip install failed.
    exit /b 1
)

python -m PyInstaller --noconfirm --onefile ^
    --name upload_liberation_mono ^
    --add-binary "libusb-1.0.dll;." ^
    --add-binary "wdi-simple.exe;." ^
    --add-data "fonts\LiberationMono-Regular.ttf;fonts" ^
    --add-data "fonts\LiberationMono-Bold.ttf;fonts" ^
    --add-data "fonts\LiberationMono-Italic.ttf;fonts" ^
    --add-data "fonts\LiberationMono-BoldItalic.ttf;fonts" ^
    upload_liberation_mono_win.py

if errorlevel 1 (
    echo ERROR: PyInstaller failed.
    exit /b 1
)

echo.
echo Built: %~dp0dist\upload_liberation_mono.exe
endlocal
