$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Push-Location -LiteralPath $projectRoot
try {
    & "$projectRoot\.venv\Scripts\python.exe" app.py
    exit $LASTEXITCODE
} finally {
    Pop-Location
}

