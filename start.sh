#!/bin/bash

# Start the client
cd client && npm run electron &

# Start the API server
cd server_api && python main.py &

# Start the Pytc-connectomics server
cd server_pytc && python main.py &

# Wait for all background jobs to finish
wait