#!/bin/bash

# Setup script for pytorch_connectomics
# Downloads the repository at commit 20ccfde (version 1.0)

set -e

PYTORCH_CONNECTOMICS_COMMIT="20ccfde"
REPO_URL="https://github.com/zudi-lin/pytorch_connectomics.git"
PYTORCH_CONNECTOMICS_DIR="pytorch_connectomics"

echo "Setting up pytorch_connectomics at commit ${PYTORCH_CONNECTOMICS_COMMIT}"

# Remove existing directory if it exists
if [ -d "${PYTORCH_CONNECTOMICS_DIR}" ]; then
    echo "Removing existing ${PYTORCH_CONNECTOMICS_DIR} directory"
    rm -rf "${PYTORCH_CONNECTOMICS_DIR}"
fi

# Clone the repository
echo "Cloning pytorch_connectomics repository..."
git clone "${REPO_URL}" "${PYTORCH_CONNECTOMICS_DIR}"

# Change to the directory and checkout the specific commit
cd "${PYTORCH_CONNECTOMICS_DIR}"
echo "Checking out commit ${PYTORCH_CONNECTOMICS_COMMIT}..."
git checkout "${PYTORCH_CONNECTOMICS_COMMIT}"

# Return to parent directory
cd ..

echo "pytorch_connectomics setup complete!"
echo "To install, run: cd ${PYTORCH_CONNECTOMICS_DIR} && pip install --editable ."
