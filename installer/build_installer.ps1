# Build UltraDown Windows installer
param(
    [switch]$Clean
)

$ErrorActionPreference = 'Stop'

Write-Host "== UltraDown Installer Builder ==" -ForegroundColor Cyan

# 1) Optionally clean
if ($Clean) {
  Write-Host "Cleaning previous builds..."
  Remove-Item -Recurse -Force ..\build, ..\dist -ErrorAction SilentlyContinue | Out-Null
}

# 2) Ensure venv active (optional)
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
  Write-Error "Python not found in PATH. Activate your venv first."
  exit 1
}

# 3) Install deps
Write-Host "Installing Python dependencies..."
pip install -r ..\requirements.txt
pip install pyinstaller

# 4) PyInstaller build (one-folder)
Write-Host "Building executable with PyInstaller..." -ForegroundColor Yellow
$specPath = Join-Path $PSScriptRoot 'pyinstaller.spec'
pyinstaller --noconfirm $specPath

# 5) Find Inno Setup Compiler
$ISCC = "C:\\Program Files (x86)\\Inno Setup 6\\ISCC.exe"
if (-not (Test-Path $ISCC)) {
  $ISCC = "C:\\Program Files\\Inno Setup 6\\ISCC.exe"
}
if (-not (Test-Path $ISCC)) {
  Write-Warning "Inno Setup not found. Install with one of the following and re-run:"
  Write-Host "  winget install Jrsoftware.InnoSetup" -ForegroundColor Gray
  Write-Host "  choco install innosetup" -ForegroundColor Gray
  exit 2
}

# 6) Compile installer
Write-Host "Compiling installer with Inno Setup..." -ForegroundColor Yellow
$issPath = Join-Path $PSScriptRoot 'innosetup.iss'
& "$ISCC" "$issPath"

Write-Host "Build complete. Find the installer EXE under installer\\dist\\installer" -ForegroundColor Green
