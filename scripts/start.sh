set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CLIENT_DIR="${ROOT_DIR}/client"

if ! command -v uv >/dev/null 2>&1; then
    echo "uv is required. Install it from https://docs.astral.sh/uv/." >&2
    exit 1
fi

if ! command -v npm >/dev/null 2>&1; then
    echo "npm is required to run the Electron client." >&2
    exit 1
fi

echo "Starting data server (port 8000)..."
uv run --directory "${ROOT_DIR}" python server_api/scripts/serve_data.py &

echo "Starting API server (port 4242)..."
PYTHONDONTWRITEBYTECODE=1 uv run --directory "${ROOT_DIR}" python -m server_api.main &

echo "Starting PyTC server (port 4243)..."
uv run --directory "${ROOT_DIR}" python -m server_pytc.main &

echo "Starting React server (port 3000)..."
pushd "${CLIENT_DIR}" >/dev/null
BROWSER=none npm start >/dev/null 2>&1 &

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
