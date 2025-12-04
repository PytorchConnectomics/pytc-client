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
    if [[ -n "${DATA_SERVER_PID:-}" ]] && ps -p "${DATA_SERVER_PID}" >/dev/null 2>&1; then
        kill "${DATA_SERVER_PID}" >/dev/null 2>&1 || true
    fi
    if [[ -n "${REACT_PID:-}" ]] && ps -p "${REACT_PID}" >/dev/null 2>&1; then
        kill "${REACT_PID}" >/dev/null 2>&1 || true
    fi
    wait || true
    exit "${exit_code}"
}

trap cleanup EXIT INT TERM

echo "Starting Data Server (port 8000)..."
uv run --directory "${ROOT_DIR}" python server_api/scripts/serve_data.py &
DATA_SERVER_PID=$!

echo "Starting API server (port 4242)..."
uv run --directory "${ROOT_DIR}" python server_api/main.py &
API_PID=$!

echo "Starting PyTC server (port 4243)..."
uv run --directory "${ROOT_DIR}" python server_pytc/main.py &
PYTC_PID=$!

echo "Starting React dev server (port 3000)..."
pushd "${CLIENT_DIR}" >/dev/null
PORT=3000 BROWSER=none npm start >/dev/null 2>&1 &
REACT_PID=$!

# Robust readiness check with progress feedback
wait_for_react() {
    local max_attempts=20
    local attempt=1
    while [[ ${attempt} -le ${max_attempts} ]]; do
        if curl -sf http://localhost:3000 >/dev/null 2>&1; then
            echo "React dev server is ready!"
            return 0
        fi
        echo "Waiting for React (attempt ${attempt}/${max_attempts})..."
        attempt=$((attempt + 1))
        sleep 1
    done
    echo "ERROR: React dev server failed to start within ${max_attempts} seconds" >&2
    return 1
}

if wait_for_react; then
    echo "Launching Electron client..."
    ENVIRONMENT=development npm run electron
else
    echo "Failed to start React dev server" >&2
    exit 1
fi

popd >/dev/null
