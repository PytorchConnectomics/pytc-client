#!/usr/bin/env bash

set -euo pipefail

if ! command -v git >/dev/null 2>&1; then
	echo "git is required to download pytorch_connectomics." >&2
	exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

PYTORCH_CONNECTOMICS_COMMIT="04c2a35e78a1a7ca1138f83a98fc3ef27097abd4"
PYTORCH_CONNECTOMICS_REF="refs/heads/pytc-client-legacy-runtime"
REPO_URL="https://github.com/PytorchConnectomics/pytorch_connectomics.git"
PYTORCH_CONNECTOMICS_DIR="${ROOT_DIR}/pytorch_connectomics"

fetch_pinned_commit() {
	git fetch --depth 1 origin "${PYTORCH_CONNECTOMICS_REF}"
	FETCHED_COMMIT="$(git rev-parse FETCH_HEAD)"
	if [ "${FETCHED_COMMIT}" != "${PYTORCH_CONNECTOMICS_COMMIT}" ]; then
		echo "${PYTORCH_CONNECTOMICS_REF} resolved to ${FETCHED_COMMIT}, expected ${PYTORCH_CONNECTOMICS_COMMIT}." >&2
		exit 1
	fi
}

if [ -d "${PYTORCH_CONNECTOMICS_DIR}/.git" ]; then
	pushd "${PYTORCH_CONNECTOMICS_DIR}" >/dev/null
	CURRENT_COMMIT="$(git rev-parse --verify HEAD 2>/dev/null || true)"
	if [ "${CURRENT_COMMIT}" != "${PYTORCH_CONNECTOMICS_COMMIT}" ]; then
		fetch_pinned_commit
		git checkout --detach "${PYTORCH_CONNECTOMICS_COMMIT}"
	fi
	popd >/dev/null
else
	if [ -d "${PYTORCH_CONNECTOMICS_DIR}" ]; then
		rmdir "${PYTORCH_CONNECTOMICS_DIR}" 2>/dev/null || {
			echo "${PYTORCH_CONNECTOMICS_DIR} exists but is not an empty Git checkout." >&2
			exit 1
		}
	fi

	mkdir -p "${PYTORCH_CONNECTOMICS_DIR}"
	git -C "${PYTORCH_CONNECTOMICS_DIR}" init --quiet
	git -C "${PYTORCH_CONNECTOMICS_DIR}" remote add origin "${REPO_URL}"
	pushd "${PYTORCH_CONNECTOMICS_DIR}" >/dev/null
	fetch_pinned_commit
	popd >/dev/null
	git -C "${PYTORCH_CONNECTOMICS_DIR}" checkout --detach "${PYTORCH_CONNECTOMICS_COMMIT}"
fi
