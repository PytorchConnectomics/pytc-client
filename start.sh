#!/bin/bash

# Get pytorch_connectomics
git submodule update --init --recursive

# Create a venv
python3 -m venv .venv
source .venv/bin/activate

# Install the required packages in /server_api/requirements.txt
pip install -r server_api/requirements.txt

# Start the API server
python3 server_api/main.py &

# Start the Pytc-connectomics server
python3 server_pytc/main.py &

# Wait for all background jobs to finish
wait