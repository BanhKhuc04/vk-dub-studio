@echo off
chcp 65001 >nul
title VK Dub Studio — by vanhkhuc
echo ===================================================
echo     DANG KHOI CHAY VK DUB STUDIO — BY VANHKHUC
echo ===================================================
set "PATH=C:\Users\khucv\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg.Essentials_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1.1-essentials_build\bin;%LOCALAPPDATA%\Microsoft\WinGet\Links;%PATH%"
cd /d D:\ToolVideo
.\.venv\Scripts\python.exe app.py
pause
