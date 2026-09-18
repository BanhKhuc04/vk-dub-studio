@echo off
chcp 65001 >nul
title KAPPAK Studio — Video Tools for Creators (by vanhkhuc)
echo ===================================================
echo     DANG KHOI CHAY KAPPAK STUDIO WEB — BY VANHKHUC
echo     Dia chi web: http://localhost:8000
echo ===================================================
for %%I in ("%~dp0..") do set "PROJECT_ROOT=%%~fI"
cd /d "%PROJECT_ROOT%"
set "PATH=%PROJECT_ROOT%\tools;%LOCALAPPDATA%\Microsoft\WinGet\Links;%PATH%"
set "PYTHONPATH=src;%PYTHONPATH%"

if not exist "%PROJECT_ROOT%\.venv\Scripts\python.exe" (
    echo [LOI] Khong tim thay Python virtual environment tai %PROJECT_ROOT%\.venv\Scripts\python.exe
    echo Vui long kiem tra hoac tao virtualenv truoc khi chay.
    pause
    exit /b 1
)

"%PROJECT_ROOT%\.venv\Scripts\python.exe" app.py %*
pause
