@echo off

REM Install dependencies in ./server_api
pip install -r server_api\requirements.txt

REM Start the API server
start cmd /C "python server_api\main.py & pause"

REM Start the Pytc-connectomics server
start cmd /C "python server_pytc\main.py & pause"
