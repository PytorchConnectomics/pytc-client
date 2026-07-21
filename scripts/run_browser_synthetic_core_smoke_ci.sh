#!/usr/bin/env bash

set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ARTIFACT_DIR="${PYTC_BROWSER_SMOKE_ARTIFACT_DIR:-${ROOT_DIR}/.ci/synthetic-browser-smoke}"
PROJECT_ROOT="${PYTC_SYNTHETIC_PROJECT_ROOT:-${ROOT_DIR}/.pytc/synthetic-core-project-ci}"
API_PORT="${PYTC_CI_API_PORT:-4242}"
REACT_PORT="${PYTC_CI_REACT_PORT:-3000}"
API_BASE_URL="http://127.0.0.1:${API_PORT}"
REACT_BASE_URL="http://127.0.0.1:${REACT_PORT}"
REPORT_PATH="${ARTIFACT_DIR}/synthetic-core-browser-smoke.json"
VIEWPORT="${PYTC_BROWSER_SMOKE_VIEWPORT:-1280x720}"

mkdir -p "${ARTIFACT_DIR}" "$(dirname "${PROJECT_ROOT}")"
rm -f \
	"${ARTIFACT_DIR}/api.pid" \
	"${ARTIFACT_DIR}/react.pid" \
	"${ARTIFACT_DIR}/synthetic-core.db" \
	"${ARTIFACT_DIR}/synthetic-core.db-shm" \
	"${ARTIFACT_DIR}/synthetic-core.db-wal" \
	"${REPORT_PATH}"

export PYTC_INITIAL_PROJECT_ROOT="${PROJECT_ROOT}"
export PYTC_INITIAL_PROJECT_KIND="synthetic"
export PYTC_INITIAL_PROJECT_TITLE="Synthetic Segmentation Core Loop"
export PYTC_INITIAL_IMAGE_PATH="${PROJECT_ROOT}/data/raw/train-01_image.h5"
export PYTC_INITIAL_LABEL_PATH="${PROJECT_ROOT}/data/seg/ground_truth/train-01_ground_truth.h5"
export PYTC_INITIAL_MASK_PATH="${PYTC_INITIAL_LABEL_PATH}"
export PYTC_INITIAL_CONFIG_PATH="${PROJECT_ROOT}/configs/Synthetic-Core-Loop-BC.yaml"
export PYTC_DATABASE_URL="sqlite:///${ARTIFACT_DIR}/synthetic-core.db"
export PYTC_API_HOST="127.0.0.1"
export PYTC_API_PORT="${API_PORT}"
export PYTC_ALLOWED_ORIGINS="${REACT_BASE_URL}"
export REACT_APP_INITIAL_PROJECT_ROOT="${PROJECT_ROOT}"
export REACT_APP_SERVER_PROTOCOL="http"
export REACT_APP_SERVER_URL="127.0.0.1:${API_PORT}"

STARTED_PIDS=()

terminate_process_tree() {
	local pid="$1"
	local child
	while IFS= read -r child; do
		[[ -n "${child}" ]] && terminate_process_tree "${child}"
	done < <(pgrep -P "${pid}" 2>/dev/null || true)
	kill "${pid}" >/dev/null 2>&1 || true
}

cleanup() {
	local exit_code=$?
	local pid
	for pid in "${STARTED_PIDS[@]:-}"; do
		if kill -0 "${pid}" >/dev/null 2>&1; then
			terminate_process_tree "${pid}"
		fi
	done
	for pid in "${STARTED_PIDS[@]:-}"; do
		wait "${pid}" >/dev/null 2>&1 || true
	done
	exit "${exit_code}"
}
trap cleanup EXIT INT TERM

wait_for_http() {
	local name="$1"
	local url="$2"
	local log_path="$3"
	local attempt
	for attempt in $(seq 1 90); do
		if curl --fail --silent --show-error "${url}" >/dev/null 2>&1; then
			echo "${name} ready at ${url}"
			return 0
		fi
		if ((attempt % 15 == 0)); then
			echo "Waiting for ${name} at ${url} (${attempt}/90)"
		fi
		sleep 1
	done
	echo "${name} failed to become ready at ${url}" >&2
	tail -n 100 "${log_path}" >&2 || true
	return 1
}

cd "${ROOT_DIR}"

uv run python scripts/create_synthetic_project.py \
	--output-dir "${PROJECT_ROOT}" \
	--reset | tee "${ARTIFACT_DIR}/fixture.log"

uv run python -m server_api.main >"${ARTIFACT_DIR}/api.log" 2>&1 &
API_PID=$!
STARTED_PIDS+=("${API_PID}")
echo "${API_PID}" >"${ARTIFACT_DIR}/api.pid"

(
	cd client
	exec env \
		BROWSER=none \
		CI=false \
		HOST=127.0.0.1 \
		PORT="${REACT_PORT}" \
		npm start
) >"${ARTIFACT_DIR}/react.log" 2>&1 &
REACT_PID=$!
STARTED_PIDS+=("${REACT_PID}")
echo "${REACT_PID}" >"${ARTIFACT_DIR}/react.pid"

wait_for_http "FastAPI" "${API_BASE_URL}/health" "${ARTIFACT_DIR}/api.log"

MOUNT_PAYLOAD="$(uv run python -c \
	'import json, os; print(json.dumps({"directory_path": os.environ["PYTC_INITIAL_PROJECT_ROOT"], "destination_path": "root", "mount_name": os.environ["PYTC_INITIAL_PROJECT_TITLE"]}))')"
curl --fail --silent --show-error \
	-X POST \
	-H "Content-Type: application/json" \
	--data-binary "${MOUNT_PAYLOAD}" \
	"${API_BASE_URL}/files/mount" >"${ARTIFACT_DIR}/mount.json"
echo "Synthetic project mounted."

wait_for_http "React" "${REACT_BASE_URL}" "${ARTIFACT_DIR}/react.log"

uv run python scripts/browser_synthetic_core_smoke.py \
	--base-url "${REACT_BASE_URL}" \
	--api-base-url "${API_BASE_URL}" \
	--timeout-ms 45000 \
	--viewport "${VIEWPORT}" \
	--screenshot "${ARTIFACT_DIR}/synthetic-core-browser-smoke.png" \
	--report "${REPORT_PATH}"
