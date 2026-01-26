# THIS IS A TEST

set -euo pipefail

API_PID=""
PYTC_PID=""

cleanup() {
    local exit_code=$?
    for pid in "${API_PID}" "${PYTC_PID}"; do
        if [[ -n "${pid}" ]] && kill -0 "${pid}" 2>/dev/null; then
            kill "${pid}" 2>/dev/null || true
        fi
    done
    wait || true
    exit "${exit_code}"
}

trap cleanup EXIT INT TERM

echo "Starting API server on :4242..."
uv run --directory /app python -m server_api.main &
API_PID=$!

echo "Starting PyTC server on :4243..."
uv run --directory /app python -m server_pytc.main &
PYTC_PID=$!

wait -n
