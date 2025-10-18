@echo off

REM Setup pytorch_connectomics if not already present
if not exist "pytorch_connectomics" (
    echo Setting up pytorch_connectomics...
    call setup_pytorch_connectomics.sh
    if errorlevel 1 (
        echo Error setting up pytorch_connectomics. Please run setup manually.
        pause
        exit /b 1
    )
    echo Installing pytorch_connectomics...
    cd pytorch_connectomics && pip install --editable . && cd ..
    if errorlevel 1 (
        echo Error installing pytorch_connectomics.
        pause
        exit /b 1
    )
)

REM Install dependencies in ./server_api
pip install -r server_api\requirements.txt
if errorlevel 1 (
    echo Error installing API dependencies.
    pause
    exit /b 1
)

REM Start the API server
echo Starting API server...
start "API Server" cmd /C "python server_api\main.py & pause"

REM Wait a moment for the first server to start
timeout /t 3 /nobreak > nul

REM Start the Pytc-connectomics server
echo Starting PyTC server...
start "PyTC Server" cmd /C "python server_pytc\main.py & pause"

echo Both servers are starting. Check the opened windows for status.
pause
