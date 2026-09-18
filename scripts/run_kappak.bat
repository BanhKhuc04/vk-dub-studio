@echo off
chcp 65001 >nul
title KAPPAK Studio — Local-first Personal Media Workspace
echo ===============================================================================
echo   DANG KHOI CHAY KAPPAK STUDIO — BY VANHKHUC
echo   Apple-Glass UI Shell ^| Local-First SQLite ^| Job Manager
echo ===============================================================================
echo.

for %%I in ("%~dp0..") do set "PROJECT_ROOT=%%~fI"
cd /d "%PROJECT_ROOT%"
set "PYTHONPATH=src;%PYTHONPATH%"

if exist "%PROJECT_ROOT%\.venv\Scripts\python.exe" (
    "%PROJECT_ROOT%\.venv\Scripts\python.exe" -m kappak.app %*
) else (
    python -m kappak.app %*
)

pause
