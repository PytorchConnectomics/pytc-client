#!/usr/bin/env bash

# Setup script for pytorch_connectomics
# Downloads the repository at commit 20ccfde (version 1.0)

set -euo pipefail

PYTORCH_CONNECTOMICS_COMMIT="20ccfde"
REPO_URL="https://github.com/zudi-lin/pytorch_connectomics.git"
PYTORCH_CONNECTOMICS_DIR="pytorch_connectomics"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${SCRIPT_DIR}"

if ! command -v git >/dev/null 2>&1; then
    echo "git is required to download pytorch_connectomics." >&2
    exit 1
fi

FORCE_REFRESH=0
while [[ $# -gt 0 ]]; do
    case "$1" in
        --force)
            FORCE_REFRESH=1
            shift
            ;;
        *)
            echo "Unknown argument: $1" >&2
            exit 1
            ;;
    esac
done

echo "Ensuring pytorch_connectomics is available at commit ${PYTORCH_CONNECTOMICS_COMMIT}"

if [ -d "${PYTORCH_CONNECTOMICS_DIR}/.git" ]; then
    echo "Existing pytorch_connectomics checkout detected."
    pushd "${PYTORCH_CONNECTOMICS_DIR}" >/dev/null

    if [ "${FORCE_REFRESH}" -eq 1 ]; then
        echo "Force refreshing repository..."
        git fetch origin
        git reset --hard "${PYTORCH_CONNECTOMICS_COMMIT}"
    else
        git fetch origin >/dev/null 2>&1 || true
        CURRENT_COMMIT="$(git rev-parse HEAD 2>/dev/null || echo "")"
        if [ "${CURRENT_COMMIT}" != "${PYTORCH_CONNECTOMICS_COMMIT}" ]; then
            echo "Checking out required commit ${PYTORCH_CONNECTOMICS_COMMIT}..."
            git checkout "${PYTORCH_CONNECTOMICS_COMMIT}"
        else
            echo "Repository already at required commit."
        fi
    fi

    popd >/dev/null
else
    echo "Cloning pytorch_connectomics repository..."
    git clone "${REPO_URL}" "${PYTORCH_CONNECTOMICS_DIR}"
    pushd "${PYTORCH_CONNECTOMICS_DIR}" >/dev/null
    echo "Checking out commit ${PYTORCH_CONNECTOMICS_COMMIT}..."
    git checkout "${PYTORCH_CONNECTOMICS_COMMIT}"
    popd >/dev/null
fi

echo "pytorch_connectomics setup complete."
echo "To install manually, run: pip install --editable ${PYTORCH_CONNECTOMICS_DIR}"
