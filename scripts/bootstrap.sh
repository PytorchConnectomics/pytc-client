#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CLIENT_DIR="${ROOT_DIR}/client"

if ! command -v uv >/dev/null 2>&1; then
    echo "uv is required. Install it from https://docs.astral.sh/uv/." >&2
    exit 1
fi

if ! command -v npm >/dev/null 2>&1; then
    echo "npm is required to install the Electron client." >&2
    exit 1
fi

echo "Synchronizing Python environment with uv..."
uv sync --python 3.11 --directory "${ROOT_DIR}"

echo "Preparing pytorch_connectomics dependency..."
"${ROOT_DIR}/setup_pytorch_connectomics.sh"

if [ -d "${ROOT_DIR}/pytorch_connectomics" ]; then
    echo "pytorch_connectomics directory found."
fi

echo "Installing frontend dependencies..."
pushd "${CLIENT_DIR}" >/dev/null
npm install
popd >/dev/null

echo "Bootstrap complete. Use ./scripts/dev.sh or ./start.sh to launch the app."
