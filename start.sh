#!/bin/bash

# Start the API server
cd server_api && python3 main.py &

# Start the Pytc-connectomics server
cd server_pytc && python3 main.py &

# Wait for all background jobs to finish
wait