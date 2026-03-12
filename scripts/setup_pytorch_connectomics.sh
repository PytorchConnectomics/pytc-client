#!/usr/bin/env bash

set -euo pipefail

if ! command -v git >/dev/null 2>&1; then
	echo "git is required to download pytorch_connectomics." >&2
	exit 1
fi

PYTORCH_CONNECTOMICS_COMMIT="0a0dceb"
REPO_URL="https://github.com/PytorchConnectomics/pytorch_connectomics.git"
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
