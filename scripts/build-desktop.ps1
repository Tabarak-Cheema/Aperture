# Build Aperture as a single-file Windows executable.
#
#   .\scripts\build-desktop.ps1
#
# Output: dist\Aperture.exe (double-click to run; no Python/Node needed)
#
# Requires Python 3.10-3.13 and Node 20+ installed at BUILD time only.

$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")

Write-Host "=== Aperture desktop build ===`n"

# 1. Build the web bundle
Push-Location apps\web
if (-not (Test-Path node_modules)) {
    Write-Host "Installing web deps..."
    npm install --legacy-peer-deps
}
Write-Host "Building web..."
npm run build
Pop-Location

# 2. Set up Python env
if (-not (Test-Path .venv)) {
    python -m venv .venv
}
.\.venv\Scripts\Activate.ps1
python -m ensurepip --upgrade | Out-Null
python -m pip install --upgrade pip
python -m pip install --prefer-binary --only-binary=":all:" -r requirements.txt
python -m pip install pyinstaller

# 3. Bundle
Write-Host "Bundling with PyInstaller..."
pyinstaller --noconfirm --clean apps\desktop\aperture.spec

if (Test-Path dist\Aperture.exe) {
    $size = (Get-Item dist\Aperture.exe).Length / 1MB
    Write-Host ("`n✓ Built: dist\Aperture.exe ({0:N1} MB)" -f $size)
    Write-Host "  Distribute this single file — users double-click and the app opens in their browser."
} else {
    Write-Error "Build produced no executable. See PyInstaller output above."
    exit 1
}
