#!/usr/bin/env bash
# Start the browser, API, and local PyTC worker as one demo.
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
API_PORT="${PYTC_AGENT_API_PORT:-4242}"
CLIENT_PORT="${PYTC_AGENT_CLIENT_PORT:-3001}"
WORKER_PORT="${PYTC_AGENT_WORKER_PORT:-4243}"
PYTHON_BIN="${PYTC_AGENT_PYTHON:-${ROOT_DIR}/.venv/bin/python}"
NODE_BIN="${PYTC_AGENT_NODE:-$(command -v node)}"
export PYTC_TEAM_MODEL="${PYTC_TEAM_MODEL-qwen3:4b}"
export PYTC_TEAM_OLLAMA_URL="${PYTC_TEAM_OLLAMA_URL:-http://127.0.0.1:11434}"
export PYTC_WORKER_URL="${PYTC_WORKER_URL:-127.0.0.1:${WORKER_PORT}}"
export PYTC_TRAINING_SUBSET_ROOT="${PYTC_TRAINING_SUBSET_ROOT:-${ROOT_DIR}/uploads/training-subsets}"
export PYTHONPATH="${ROOT_DIR}/pytorch_connectomics${PYTHONPATH:+:${PYTHONPATH}}"
export OMP_NUM_THREADS="${OMP_NUM_THREADS:-2}"
export MKL_NUM_THREADS="${MKL_NUM_THREADS:-2}"
export PYTC_ALLOWED_ORIGINS="http://127.0.0.1:${CLIENT_PORT},http://localhost:${CLIENT_PORT}"
export PYTC_DEV_API_TARGET="http://127.0.0.1:${API_PORT}"
export REACT_APP_API_BASE_URL="http://127.0.0.1:${CLIENT_PORT}/backend"
cd "${ROOT_DIR}"
test -f pytorch_connectomics/scripts/main.py || { echo "Initialize the pinned pytorch_connectomics checkout before starting." >&2; exit 1; }
"${PYTHON_BIN}" - "${API_PORT}" "${CLIENT_PORT}" "${WORKER_PORT}" <<'PY'
import socket, sys
sockets=[]
try:
    for port in sys.argv[1:]:
        sock=socket.socket(); sockets.append(sock)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(('127.0.0.1',int(port)))
except OSError as e:
    raise SystemExit(f'Demo port unavailable: {e}. Choose free PYTC_AGENT_*_PORT values.')
finally:
    for sock in sockets: sock.close()
PY
mkdir -p .logs/agent-prototype
PIDS=()
cleanup() { for pid in "${PIDS[@]}"; do kill "$pid" 2>/dev/null || true; done; }
trap cleanup EXIT INT TERM
"${PYTHON_BIN}" -m uvicorn server_pytc.main:app --host 127.0.0.1 --port "${WORKER_PORT}" > .logs/agent-prototype/worker.log 2>&1 &
PIDS+=("$!")
"${PYTHON_BIN}" -m uvicorn server_api.main:app --host 127.0.0.1 --port "${API_PORT}" > .logs/agent-prototype/api.log 2>&1 &
PIDS+=("$!")
(cd client; exec env HOST=127.0.0.1 BROWSER=none PORT="${CLIENT_PORT}" "${NODE_BIN}" node_modules/react-scripts/scripts/start.js) > .logs/agent-prototype/client.log 2>&1 &
PIDS+=("$!")
echo "App: http://127.0.0.1:${CLIENT_PORT}"
echo "API: ${REACT_APP_API_BASE_URL}; logs: ${ROOT_DIR}/.logs/agent-prototype"
while true; do
  for pid in "${PIDS[@]}"; do
    if ! kill -0 "$pid" 2>/dev/null; then echo 'A demo service exited; inspect its log.' >&2; exit 1; fi
  done
  sleep 2
done
