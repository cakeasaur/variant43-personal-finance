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
  # In CI we already have Python configured (actions/setup-python).
  # Use the current `python` instead of `py` (which may point to 3.14+).
  $Py = "python"
}

& $Py -m pip install --upgrade pip
& $Py -m pip install -r requirements/app.txt -r requirements/dev.txt

Write-Host "Running checks..." -ForegroundColor Cyan
& $Py -m ruff check .
& $Py -m pytest -q

Write-Host "Building with PyInstaller..." -ForegroundColor Cyan

# Kivy apps need assets packaged alongside the executable. PyInstaller has built-in
# hooks for Kivy; avoid overly broad "collect-all kivy" because it can trip on
# optional subpackages (e.g. gstplayer).
#
# We build from `main.py` to keep a stable entrypoint across desktop/Android.
& $Py -m PyInstaller --noconfirm --clean --windowed `
  --name "PersonalFinance" `
  --add-data "assets;assets" `
  --hidden-import "kivy_deps.sdl2" `
  --hidden-import "kivy_deps.glew" `
  --hidden-import "kivy_deps.angle" `
  main.py

Write-Host "Done. Output: dist\\PersonalFinance\\PersonalFinance.exe" -ForegroundColor Green

