# Start the suite on Windows. Creates a virtual environment on first run, and
# refreshes it whenever requirements.txt changes.
#
# See run.sh for why the refresh is here: installing only when .venv is absent
# meant that pulling a commit which added an optional, guarded dependency left
# the feature silently not working, with nothing on screen to say why.
$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

$stamp = ".venv\.requirements-sha"
function Get-RequirementsHash {
  (Get-FileHash -Algorithm SHA256 -Path "requirements.txt").Hash
}

if (-not (Test-Path ".venv")) {
  Write-Host "First run - creating a virtual environment and installing dependencies."
  python -m venv .venv
  & ".\.venv\Scripts\python.exe" -m pip install --quiet --upgrade pip
  & ".\.venv\Scripts\python.exe" -m pip install --quiet -r requirements.txt
  Get-RequirementsHash | Set-Content -Path $stamp
}
elseif (-not (Test-Path $stamp) -or ((Get-Content -Path $stamp -Raw).Trim() -ne (Get-RequirementsHash))) {
  Write-Host "Dependencies changed since the last run - updating."
  & ".\.venv\Scripts\python.exe" -m pip install --quiet -r requirements.txt
  Get-RequirementsHash | Set-Content -Path $stamp
}

& ".\.venv\Scripts\python.exe" -m app.main
