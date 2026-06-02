$projectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $projectRoot

if (-not (Test-Path ".\.venv")) {
    python -m venv .venv
}

& ".\.venv\Scripts\python.exe" -m pip install --upgrade pip
& ".\.venv\Scripts\python.exe" -m pip install -r requirements.txt
& ".\.venv\Scripts\python.exe" scripts\seed_sample.py

Write-Host ""
Write-Host "Setup complete."
Write-Host "Run dashboard:"
Write-Host ".\scripts\start_dashboard.ps1"
