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

if ! command -v git >/dev/null 2>&1; then
    echo "git is required to download pytorch_connectomics." >&2
    exit 1
fi

echo "Synchronizing Python environment with uv..."
uv sync --python 3.11 --directory "${ROOT_DIR}"

echo "Preparing pytorch_connectomics dependency..."

PYTORCH_CONNECTOMICS_COMMIT="20ccfde"
REPO_URL="https://github.com/zudi-lin/pytorch_connectomics.git"
PYTORCH_CONNECTOMICS_DIR="pytorch_connectomics"

if [ -d "${PYTORCH_CONNECTOMICS_DIR}/.git" ]; then
    pushd "${PYTORCH_CONNECTOMICS_DIR}" >/dev/null
    git fetch origin >/dev/null 2>&1 || true
    CURRENT_COMMIT="$(git rev-parse HEAD 2>/dev/null || echo "")"
    if [ "${CURRENT_COMMIT}" != "${PYTORCH_CONNECTOMICS_COMMIT}" ]; then
        git checkout "${PYTORCH_CONNECTOMICS_COMMIT}"
    fi
    popd >/dev/null
else
    git clone "${REPO_URL}" "${PYTORCH_CONNECTOMICS_DIR}"
    pushd "${PYTORCH_CONNECTOMICS_DIR}" >/dev/null
    git checkout "${PYTORCH_CONNECTOMICS_COMMIT}"
    popd >/dev/null
fi

echo "Installing frontend dependencies..."
pushd "${CLIENT_DIR}" >/dev/null
npm install
popd >/dev/null

echo "Bootstrap complete. Run scripts/start.sh to launch the app."
