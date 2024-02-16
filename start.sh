#!/bin/bash

# Start the API server
python3 server_api/main.py &

# Start the Pytc-connectomics server
python3 server_pytc/main.py &

# Wait for all background jobs to finish
wait