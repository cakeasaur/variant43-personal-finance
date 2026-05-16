param(
  [string]$Python = "py -3.12",
  [switch]$NoVenv
)

$ErrorActionPreference = "Stop"

Write-Host "== Personal Finance (Variant 43) :: Windows build ==" -ForegroundColor Cyan

if (-not $NoVenv) {
  if (-not (Test-Path ".venv")) {
    & $Python -m venv .venv
  }
  .\.venv\Scripts\Activate.ps1
  $Py = "python"
} else {
  $Py = "python"
}

& $Py -m pip install --upgrade pip
& $Py -m pip install -r requirements/app.txt -r requirements/dev.txt

Write-Host "Running checks..." -ForegroundColor Cyan
& $Py -m ruff check .
& $Py -m pytest -q

Write-Host "Building with flet build..." -ForegroundColor Cyan
flet build windows --project PersonalFinance

Write-Host "Done. Output: build\windows\PersonalFinance.exe" -ForegroundColor Green
