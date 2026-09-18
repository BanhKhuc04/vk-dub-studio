@echo off
chcp 65001 >nul
title KAPPAK Studio — Local-first Personal Media Workspace
echo ===============================================================================
echo   DANG KHOI CHAY KAPPAK STUDIO — BY VANHKHUC
echo   Apple-Glass UI Shell ^| Local-First SQLite ^| Job Manager
echo ===============================================================================
echo.

cd /d "%~dp0"
set "PYTHONPATH=src;%PYTHONPATH%"

if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" -m kappak.app
) else (
    python -m kappak.app
)

pause
