#!/usr/bin/env bash

set -euo pipefail

# Prefer Homebrew's Node over nvm to avoid version conflicts
export PATH="/opt/homebrew/bin:$PATH"
export OLLAMA_BASE_URL="http://cscigpu08.bc.edu:11434"
export OLLAMA_MODEL="gpt-oss:20b"
export OLLAMA_EMBED_MODEL="qwen3-embedding:8b"

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CLIENT_DIR="${ROOT_DIR}/client"
LOG_DIR="${ROOT_DIR}/.logs/start"

if ! command -v uv >/dev/null 2>&1; then
	echo "uv is required. Install it from https://docs.astral.sh/uv/." >&2
	exit 1
fi

if ! command -v npm >/dev/null 2>&1; then
	echo "npm is required to run the Electron client." >&2
	exit 1
fi

mkdir -p "${LOG_DIR}"

STARTED_PIDS=()

relative_log_path() {
	local path="$1"
	if [[ "${path}" == "${ROOT_DIR}"/* ]]; then
		echo "${path#${ROOT_DIR}/}"
	else
		echo "${path}"
	fi
}

port_is_listening() {
	local port="$1"
	lsof -tiTCP:"${port}" -sTCP:LISTEN >/dev/null 2>&1
}

wait_for_http() {
	local name="$1"
	local url="$2"
	local max_attempts="${3:-30}"
	local attempt=1

	while [[ ${attempt} -le ${max_attempts} ]]; do
		if curl -sf "${url}" >/dev/null 2>&1; then
			return 0
		fi
		attempt=$((attempt + 1))
		sleep 1
	done

	echo "ERROR: ${name} did not become ready at ${url}" >&2
	return 1
}

start_service() {
	local name="$1"
	local port="$2"
	local health_url="$3"
	local log_file="$4"
	shift 4

	if port_is_listening "${port}"; then
		if wait_for_http "${name}" "${health_url}" 5; then
			echo "${name} already running on :${port}; reusing existing service."
			return 0
		fi
		echo "ERROR: Port ${port} is already in use, but ${name} did not respond at ${health_url}." >&2
		return 1
	fi

	: >"${log_file}"
	"$@" >"${log_file}" 2>&1 &
	local pid=$!
	STARTED_PIDS+=("${pid}")
	echo "${name} starting on :${port} (pid ${pid}; log: $(relative_log_path "${log_file}"))"

	if ! wait_for_http "${name}" "${health_url}" 30; then
		echo "Recent ${name} log output:" >&2
		tail -n 40 "${log_file}" >&2 || true
		return 1
	fi

	echo "${name} ready on :${port}"
}

cleanup() {
	local exit_code=$?
	local pid
	for pid in "${STARTED_PIDS[@]:-}"; do
		if ps -p "${pid}" >/dev/null 2>&1; then
			kill "${pid}" >/dev/null 2>&1 || true
		fi
	done
	wait || true
	exit "${exit_code}"
}

trap cleanup EXIT INT TERM

start_service \
	"Data server" \
	8000 \
	"http://localhost:8000/" \
	"${LOG_DIR}/data-server.log" \
	uv run --directory "${ROOT_DIR}" python server_api/scripts/serve_data.py

start_service \
	"API server" \
	4242 \
	"http://localhost:4242/health" \
	"${LOG_DIR}/api-server.log" \
	env PYTHONDONTWRITEBYTECODE=1 uv run --directory "${ROOT_DIR}" python -m server_api.main

start_service \
	"PyTC server" \
	4243 \
	"http://localhost:4243/hello" \
	"${LOG_DIR}/pytc-server.log" \
	uv run --directory "${ROOT_DIR}" python -m server_pytc.main

pushd "${CLIENT_DIR}" >/dev/null
if [[ "${SKIP_CLIENT_BUILD:-0}" != "1" ]]; then
	BUILD_LOG="${LOG_DIR}/react-build.log"
	echo "Building React client (log: $(relative_log_path "${BUILD_LOG}"))..."
	if npm run build >"${BUILD_LOG}" 2>&1; then
		echo "React build complete"
	else
		echo "ERROR: React build failed. Recent log output:" >&2
		tail -n 60 "${BUILD_LOG}" >&2 || true
		exit 1
	fi
fi

REACT_LOG="${LOG_DIR}/react-dev.log"
if port_is_listening 3000; then
	if curl -sf http://localhost:3000 >/dev/null 2>&1; then
		echo "React server already running on :3000; reusing existing service."
	else
		echo "ERROR: Port 3000 is already in use, but React did not respond." >&2
		exit 1
	fi
else
	: >"${REACT_LOG}"
	echo "React server starting on :3000 (log: $(relative_log_path "${REACT_LOG}"))"
	BROWSER=none npm start >"${REACT_LOG}" 2>&1 &
	STARTED_PIDS+=("$!")
fi

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
	echo "Startup logs are under $(relative_log_path "${LOG_DIR}")"
	echo "Starting Electron client..."
	ENVIRONMENT=development npm run electron
else
	echo "Failed to start React server" >&2
	exit 1
fi

popd >/dev/null
