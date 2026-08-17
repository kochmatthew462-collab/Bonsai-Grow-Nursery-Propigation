# Start the suite on Windows. Creates a virtual environment on first run.
$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

if (-not (Test-Path ".venv")) {
  Write-Host "First run - creating a virtual environment and installing dependencies."
  python -m venv .venv
  & ".\.venv\Scripts\python.exe" -m pip install --quiet --upgrade pip
  & ".\.venv\Scripts\python.exe" -m pip install --quiet -r requirements.txt
}

& ".\.venv\Scripts\python.exe" -m app.main
