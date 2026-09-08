@echo off
setlocal

:: 1. If installed as desktop app (PyInstaller executable)
if exist "%~dp0..\..\VK Dub Studio.exe" (
    "%~dp0..\..\VK Dub Studio.exe" --native-host %*
    exit /b %ERRORLEVEL%
)

if exist "%~dp0..\VK Dub Studio.exe" (
    "%~dp0..\VK Dub Studio.exe" --native-host %*
    exit /b %ERRORLEVEL%
)

:: 2. Prefer workspace virtualenv python if present
if exist "d:\ToolVideo\.venv\Scripts\python.exe" (
    set "PYTHON_EXE=d:\ToolVideo\.venv\Scripts\python.exe"
    goto :RUN
)

if exist "%~dp0..\..\.venv\Scripts\python.exe" (
    set "PYTHON_EXE=%~dp0..\..\.venv\Scripts\python.exe"
    goto :RUN
)

set "PYTHON_EXE=python"

:RUN
"%PYTHON_EXE%" -u "%~dp0vkdub_host.py" %*
