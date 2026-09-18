@echo off
chcp 65001 >nul
title KAPPAK Studio — Video Tools for Creators (by vanhkhuc)
echo ===================================================
echo     DANG KHOI CHAY KAPPAK STUDIO — BY VANHKHUC
echo     Video Tools for Creators
echo ===================================================
set "PATH=C:\Users\khucv\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg.Essentials_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1.1-essentials_build\bin;%LOCALAPPDATA%\Microsoft\WinGet\Links;%PATH%"
cd /d "%~dp0"
.\.venv\Scripts\python.exe app.py
pause
