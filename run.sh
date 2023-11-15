#!/bin/bash
# Change permission before use
# chmod +x run.sh

# Start the React app
cd client
yarn electron &

# Start the API Server
source .venv/bin/activate
cd ./server_api
python main.py &

# Start the Pytc Server
cd ./server_pytc
python main.py &

# Wait for all processes to finish
wait