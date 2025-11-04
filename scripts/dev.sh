#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CLIENT_DIR="${ROOT_DIR}/client"

if ! command -v uv >/dev/null 2>&1; then
    echo "uv is required. Run scripts/bootstrap.sh first." >&2
    exit 1
fi

if ! command -v npm >/dev/null 2>&1; then
    echo "npm is required to launch the Electron client." >&2
    exit 1
fi

cleanup() {
    local exit_code=$?
    if [[ -n "${API_PID:-}" ]] && ps -p "${API_PID}" >/dev/null 2>&1; then
        kill "${API_PID}" >/dev/null 2>&1 || true
    fi
    if [[ -n "${PYTC_PID:-}" ]] && ps -p "${PYTC_PID}" >/dev/null 2>&1; then
        kill "${PYTC_PID}" >/dev/null 2>&1 || true
    fi
    wait || true
    exit "${exit_code}"
}

trap cleanup EXIT INT TERM

echo "Starting API server..."
uv run --directory "${ROOT_DIR}" python server_api/main.py &
API_PID=$!

echo "Starting PyTC server..."
uv run --directory "${ROOT_DIR}" python server_pytc/main.py &
PYTC_PID=$!

echo "Launching Electron client..."
pushd "${CLIENT_DIR}" >/dev/null
npm run electron
popd >/dev/null
