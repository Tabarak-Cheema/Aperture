#!/usr/bin/env bash
# Build Aperture as a single-file executable for the current OS.
#   ./scripts/build-desktop.sh
# Output on Linux:  dist/Aperture         (chmod +x, double-click)
# Output on macOS:  dist/Aperture         (chmod +x, double-click; no .app bundle)
set -euo pipefail
cd "$(dirname "$0")/.."

echo "=== Aperture desktop build ==="

pushd apps/web >/dev/null
[[ -d node_modules ]] || npm install --legacy-peer-deps
npm run build
popd >/dev/null

[[ -d .venv ]] || python3 -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate
python -m ensurepip --upgrade >/dev/null 2>&1 || true
python -m pip install --upgrade pip >/dev/null
python -m pip install --prefer-binary --only-binary=:all: -r requirements.txt
python -m pip install pyinstaller

pyinstaller --noconfirm --clean apps/desktop/aperture.spec

if [[ -f dist/Aperture ]]; then
    bytes=$(stat -c%s dist/Aperture 2>/dev/null || stat -f%z dist/Aperture)
    mb=$((bytes / 1024 / 1024))
    echo
    echo "✓ Built: dist/Aperture (${mb} MB)"
    echo "  Distribute this single file."
else
    echo "Build produced no executable. See PyInstaller output above."
    exit 1
fi
