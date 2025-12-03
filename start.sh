#!/usr/bin/env bash

# Wrapper script that runs the main dev script
# Neuroglancer Python server is no longer started here as we are using the web client

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Run the main dev script
exec "${ROOT_DIR}/scripts/dev.sh" "$@"
