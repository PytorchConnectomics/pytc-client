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
    if [[ -n "${REACT_PID:-}" ]] && ps -p "${REACT_PID}" >/dev/null 2>&1; then
        kill "${REACT_PID}" >/dev/null 2>&1 || true
    fi
    if [[ -n "${DATA_SERVER_PID:-}" ]] && ps -p "${DATA_SERVER_PID}" >/dev/null 2>&1; then
        kill "${DATA_SERVER_PID}" >/dev/null 2>&1 || true
    fi
    wait || true
    exit "${exit_code}"
}

trap cleanup EXIT INT TERM

echo "Starting Data Server (port 8000)..."
uv run --directory "${ROOT_DIR}" python server_api/scripts/serve_data.py &
DATA_SERVER_PID=$!

echo "Starting API server..."
uv run --directory "${ROOT_DIR}" python server_api/main.py &
API_PID=$!

echo "Starting PyTC server..."
uv run --directory "${ROOT_DIR}" python server_pytc/main.py &
PYTC_PID=$!

echo "Starting React server..."
pushd "${CLIENT_DIR}" >/dev/null
BROWSER=none npm start >/dev/null 2>&1 &
REACT_PID=$!
wait_for_react() {
    local max_attempts=30
    local attempt=1
    until curl -sf http://localhost:3000 >/dev/null 2>&1; do
        if [[ ${attempt} -ge ${max_attempts} ]]; then
            return 1
        fi
        attempt=$((attempt + 1))
        sleep 1
    done
    return 0
}
if wait_for_react; then
    echo "Starting Electron client..."
    ENVIRONMENT=development npm run electron
else
    echo "Failed to start React server"
fi
popd >/dev/null
