#!/bin/bash
for port in 3000 4242 4243 8000; do
    fuser -k ${port}/tcp
done

pkill -f "uvicorn"
pkill -f "serve_data.py"
pkill -f "electron"

echo "Ports and processes cleared."

