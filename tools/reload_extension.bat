@echo off
setlocal

echo ===============================================================================
echo   VK Dub Studio -- Browser Extension Developer Reload and Setup Tool
echo ===============================================================================
echo.

for %%I in ("%~dp0..") do set "PROJECT_ROOT=%%~fI"
set "EXT_DIR=%PROJECT_ROOT%\apps\browser-extension"
set "EXTENSION_ID=bnpmffibedppchkljkcaidgijekgfmgl"

echo [1] Kiem tra va dang ky Native Messaging Host cho Edge va Chrome...
if exist "%PROJECT_ROOT%\.venv\Scripts\python.exe" (
    "%PROJECT_ROOT%\.venv\Scripts\python.exe" "%PROJECT_ROOT%\tools\native_host\register_host.py"
) else (
    python "%PROJECT_ROOT%\tools\native_host\register_host.py"
)
echo.

echo [2] Thong tin cai dat Extension (Developer Mode):
echo     Thu muc Extension: %EXT_DIR%
echo     Extension ID:      %EXTENSION_ID%
echo.
echo     Huong dan cho Microsoft Edge:
echo       1. Mo trinh duyet, truy cap: edge://extensions/
echo       2. Bat cong tac "Che do cho nha phat trien" (Developer mode).
echo       3. Bam nut "Tai ban mo rong da giai nen" (Load unpacked).
echo       4. Chon thu muc: %EXT_DIR%
echo.
echo     Huong dan cho Google Chrome:
echo       1. Mo trinh duyet, truy cap: chrome://extensions/
echo       2. Bat cong tac "Developer mode" o goc tren ben phai.
echo       3. Bam nut "Load unpacked" o goc tren ben trai.
echo       4. Chon thu muc: %EXT_DIR%
echo.

echo [3] Huong dan cap nhat (Reload):
echo     Khi sua ma nguon extension, bam nut Reload (bieu tuong xoay tron)
echo     ngay ben canh VK Dub Studio Bridge tren trang edge://extensions
echo     hoac chrome://extensions de cap nhat ngay lap tuc.
echo.
echo ===============================================================================
echo   Hoan tat setup / huong dan reload extension.
echo ===============================================================================
