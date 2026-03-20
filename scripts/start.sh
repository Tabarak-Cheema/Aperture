#!/usr/bin/env bash
# Aperture bootstrap for Linux / macOS. Uses uv (auto-installed) to pick the
# right Python and build the venv in milliseconds.
set -euo pipefail
cd "$(dirname "$0")/.."

echo
echo "=== Aperture ==="
echo "Working dir: $PWD"
echo

# 1. uv --------------------------------------------------------------------
if ! command -v uv >/dev/null 2>&1; then
    echo "Installing uv (one-time)..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
fi
command -v uv >/dev/null 2>&1 || { echo "[ERROR] uv install failed"; exit 1; }

# 2. Python 3.12 -----------------------------------------------------------
uv python install 3.12 >/dev/null 2>&1 || true

# 3. venv ------------------------------------------------------------------
if [[ -d .venv ]]; then
    v=$(.venv/bin/python -c 'import sys;print(sys.version_info.minor)' 2>/dev/null || echo 0)
    if [[ "$v" -lt 10 || "$v" -ge 14 ]]; then
        echo "Recreating .venv (previous one used Python 3.$v)..."
        rm -rf .venv
    fi
fi
[[ -d .venv ]] || uv venv --python 3.12 .venv

# 4. Python deps -----------------------------------------------------------
echo
echo "=== Installing Python requirements ==="
uv pip install --python .venv/bin/python --only-binary=:all: -r requirements.txt

# 5. Node / npm ------------------------------------------------------------
for cmd in node npm; do
    command -v "$cmd" >/dev/null 2>&1 || { echo "[ERROR] $cmd not on PATH"; exit 1; }
done

pushd apps/web >/dev/null
[[ -d node_modules ]] || npm install --legacy-peer-deps
popd >/dev/null

export PYTHONPATH="packages/aqir:packages/catalog:packages/llm_gateway:services/compile:services/query:services/ingest:services/insight:apps/server"

# 6. Launch ----------------------------------------------------------------
pids=()
cleanup() { kill "${pids[@]}" 2>/dev/null || true; }
trap cleanup EXIT

.venv/bin/python -m uvicorn apps.server.aperture_server.main:app --port 8000 --reload &  pids+=($!)
sleep 1
pushd apps/web >/dev/null
npm run dev &  pids+=($!)
popd >/dev/null

echo
echo "Aperture is up:  http://localhost:5173"
echo "API docs:        http://localhost:8000/docs"
echo "Ctrl+C to stop."
wait
