#!/usr/bin/env bash
# Launch the app with task-script settings (cluster host, folders) from .task-dsl.env.
# Copy .task-dsl.env.example to .task-dsl.env and fill in your own values first.
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ ! -f "${ROOT_DIR}/.task-dsl.env" ]]; then
	echo "Missing .task-dsl.env. Copy .task-dsl.env.example and fill it in." >&2
	exit 1
fi
set -a
# shellcheck disable=SC1091
source "${ROOT_DIR}/.task-dsl.env"
set +a
if ! curl -s -m 2 "${OLLAMA_BASE_URL:-http://127.0.0.1:11434}/api/tags" >/dev/null; then
	echo "Starting Ollama for script drafting..."
	(ollama serve >/dev/null 2>&1 &)
fi
exec "${ROOT_DIR}/scripts/dev.sh"
