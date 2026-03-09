#!/usr/bin/env bash

set -euo pipefail

# Prefer Homebrew's Node over nvm to avoid version conflicts
export PATH="/opt/homebrew/bin:$PATH"
export OLLAMA_BASE_URL="http://cscigpu08.bc.edu:11434"
export OLLAMA_MODEL="gpt-oss:20b"
export OLLAMA_EMBED_MODEL="qwen3-embedding:8b"

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CLIENT_DIR="${ROOT_DIR}/client"
PORTS=(8000 4242 4243 3000)
PIDS=()
CLEANED_UP=0

if ! command -v uv >/dev/null 2>&1; then
	echo "uv is required. Install it from https://docs.astral.sh/uv/." >&2
	exit 1
fi

if ! command -v npm >/dev/null 2>&1; then
	echo "npm is required to run the Electron client." >&2
	exit 1
fi

kill_port_listeners() {
	local port="$1"
	local pids
	pids="$(lsof -tiTCP:"${port}" -sTCP:LISTEN 2>/dev/null || true)"
	if [[ -z "${pids}" ]]; then
		return
	fi

	echo "Stopping stale process(es) on port ${port}: ${pids}"
	kill ${pids} 2>/dev/null || true
	sleep 0.3

	local stubborn
	stubborn="$(lsof -tiTCP:"${port}" -sTCP:LISTEN 2>/dev/null || true)"
	if [[ -n "${stubborn}" ]]; then
		echo "Force killing stubborn process(es) on port ${port}: ${stubborn}"
		kill -9 ${stubborn} 2>/dev/null || true
	fi
}

cleanup() {
	if [[ "${CLEANED_UP}" -eq 1 ]]; then
		return
	fi
	CLEANED_UP=1

	echo "Shutting down background services..."
	for pid in "${PIDS[@]:-}"; do
		if [[ -n "${pid}" ]] && kill -0 "${pid}" 2>/dev/null; then
			kill "${pid}" 2>/dev/null || true
		fi
	done

	sleep 0.3
	for port in "${PORTS[@]}"; do
		kill_port_listeners "${port}"
	done
}

trap cleanup EXIT INT TERM

echo "Cleaning stale listeners before startup..."
for port in "${PORTS[@]}"; do
	kill_port_listeners "${port}"
done

echo "Starting data server (port 8000)..."
uv run --directory "${ROOT_DIR}" python server_api/scripts/serve_data.py &
PIDS+=("$!")

echo "Starting API server (port 4242)..."
PYTHONDONTWRITEBYTECODE=1 uv run --directory "${ROOT_DIR}" python -m server_api.main &
PIDS+=("$!")

echo "Starting PyTC server (port 4243)..."
uv run --directory "${ROOT_DIR}" python -m server_pytc.main &
PIDS+=("$!")

echo "Starting React server (port 3000)..."
pushd "${CLIENT_DIR}" >/dev/null
BROWSER=none npm start >/dev/null 2>&1 &
PIDS+=("$!")

wait_for_react() {
	local max_attempts=60
	local attempt=1
	while [[ ${attempt} -le ${max_attempts} ]]; do
		if curl -sf http://localhost:3000 >/dev/null 2>&1; then
			echo "React is ready"
			return 0
		fi
		echo "Waiting for React (attempt ${attempt}/${max_attempts})..."
		attempt=$((attempt + 1))
		sleep 1
	done
	echo "ERROR: React server failed to start within ${max_attempts} seconds" >&2
	return 1
}

if wait_for_react; then
	echo "Starting Electron client..."
	ENVIRONMENT=development npm run electron
else
	echo "Failed to start React server" >&2
	exit 1
fi

popd >/dev/null
