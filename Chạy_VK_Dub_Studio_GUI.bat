@echo off
chcp 65001 >nul
title VK Dub Studio v2.1.18 — Desktop GUI
echo ===================================================
echo     DANG KHOI CHAY VK DUB STUDIO v2.1.18 (GUI)
echo     Tac gia: vanhkhuc.dev
echo ===================================================
cd /d "%~dp0"
set "PATH=%~dp0tools;%LOCALAPPDATA%\Microsoft\WinGet\Links;%PATH%"
set "PYTHONPATH=src;%PYTHONPATH%"

if not exist ".venv\Scripts\python.exe" (
    echo [LOI] Khong tim thay Python tai .venv\Scripts\python.exe
    pause
    exit /b 1
)

start "" ".venv\Scripts\python.exe" app.py --gui
exit
