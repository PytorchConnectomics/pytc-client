#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CLIENT_DIR="${ROOT_DIR}/client"
DEFAULT_OLLAMA_BASE_URL="http://127.0.0.1:11434"
DEFAULT_OLLAMA_MODEL="qwen3.6:27b"
DEFAULT_OLLAMA_EMBED_MODEL="qwen3-embedding:8b"
export PYTC_UNLOAD_OLLAMA_BEFORE_TRAINING="${PYTC_UNLOAD_OLLAMA_BEFORE_TRAINING:-0}"

if ! command -v uv >/dev/null 2>&1; then
	echo "uv is required. Run scripts/bootstrap.sh first." >&2
	exit 1
fi

if ! command -v npm >/dev/null 2>&1; then
	echo "npm is required to launch the Electron client." >&2
	exit 1
fi

# Stop a process and everything it started. `npm start` runs the React server as a
# child process and does not always pass signals on, so killing only npm's PID can
# leave the server orphaned and still holding port 3000.
stop_tree() {
	local pid="$1" child
	[[ -n "${pid}" ]] || return 0
	for child in $(pgrep -P "${pid}" 2>/dev/null); do
		stop_tree "${child}"
	done
	kill "${pid}" >/dev/null 2>&1 || true
}

cleanup() {
	local exit_code=$?
	stop_tree "${API_PID:-}"
	stop_tree "${PYTC_PID:-}"
	stop_tree "${DATA_SERVER_PID:-}"
	stop_tree "${REACT_PID:-}"
	wait || true
	exit "${exit_code}"
}

trap cleanup EXIT INT TERM

echo "Starting Data Server (port 8000)..."
uv run --directory "${ROOT_DIR}" python server_api/scripts/serve_data.py &
DATA_SERVER_PID=$!

echo "Starting API server (port 4242)..."
OLLAMA_BASE_URL="${OLLAMA_BASE_URL:-${DEFAULT_OLLAMA_BASE_URL}}" \
	OLLAMA_MODEL="${OLLAMA_MODEL:-${DEFAULT_OLLAMA_MODEL}}" \
	PYTC_WORKFLOW_INTENT_MODEL="${PYTC_WORKFLOW_INTENT_MODEL:-${OLLAMA_MODEL:-${DEFAULT_OLLAMA_MODEL}}}" \
	OLLAMA_EMBED_MODEL="${OLLAMA_EMBED_MODEL:-${DEFAULT_OLLAMA_EMBED_MODEL}}" \
	PYTHONDONTWRITEBYTECODE=1 uv run --directory "${ROOT_DIR}" python -m server_api.main &
API_PID=$!

echo "Starting PyTC server (port 4243)..."
uv run --directory "${ROOT_DIR}" python -m server_pytc.main &
PYTC_PID=$!

echo "Starting React dev server (port 3000)..."
pushd "${CLIENT_DIR}" >/dev/null
PORT=3000 BROWSER=none npm start >react.log 2>&1 &
REACT_PID=$!

# Robust readiness check with progress feedback
wait_for_react() {
	local max_attempts=60
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
	echo "Check client/react.log for details." >&2
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
