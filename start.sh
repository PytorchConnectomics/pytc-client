#!/bin/bash

# Setup pytorch_connectomics if not already present
if [ ! -d "pytorch_connectomics" ]; then
    echo "Setting up pytorch_connectomics..."
    ./setup_pytorch_connectomics.sh
    echo "Installing pytorch_connectomics..."
    cd pytorch_connectomics && pip3 install --editable . && cd ..
fi

# Install dependencies in ./server_api
pip3 install -r server_api/requirements.txt

# Start the API server
python3 server_api/main.py &

# Start the Pytc-connectomics server
python3 server_pytc/main.py &

# Wait for all background jobs to finish
wait