import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from server_pytc.services.model import (
    get_tensorboard,
    initialize_tensorboard,
    start_inference,
    start_training,
    stop_inference,
    stop_training,
)

print("\n" + "="*80)
print("SERVER_PYTC STARTING UP")
print(f"Python executable: {__import__('sys').executable}")
print(f"Working directory: {__import__('os').getcwd()}")
print("="*80 + "\n")

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/hello")
def hello():
    return {"hello"}


@app.post("/start_model_training")
async def start_model_training(req: Request):
    print("\n========== SERVER_PYTC: START_MODEL_TRAINING ENDPOINT CALLED ==========")
    req = await req.json()
    print(f"[SERVER_PYTC] Received request payload keys: {list(req.keys())}")
    print(f"[SERVER_PYTC] Arguments: {req.get('arguments', {})}")
    print(f"[SERVER_PYTC] Log path: {req.get('logPath', 'NOT PROVIDED')}")
    print(f"[SERVER_PYTC] Training config preview: {req.get('trainingConfig', '')[:200]}...")
    
    try:
        print("[SERVER_PYTC] Calling start_training()...")
        result = start_training(req)
        print(f"[SERVER_PYTC] start_training() returned: {result}")
        print("========== SERVER_PYTC: END OF START_MODEL_TRAINING ==========\n")
        return result or {"status": "started"}
    except Exception as e:
        print(f"[SERVER_PYTC] ✗ ERROR in start_training: {type(e).__name__}: {str(e)}")
        import traceback
        print(traceback.format_exc())
        print("========== SERVER_PYTC: END OF START_MODEL_TRAINING (WITH ERROR) ==========\n")
        raise


@app.post("/stop_model_training")
async def stop_model_training():
    print("Stop model training")
    return stop_training()


@app.get("/training_status")
async def get_training_status():
    """Check if training process is still running"""
    from server_pytc.services.model import _training_process
    
    if _training_process is None:
        return {"isRunning": False, "message": "No training process"}
    
    poll_result = _training_process.poll()
    is_running = poll_result is None
    
    return {
        "isRunning": is_running,
        "pid": _training_process.pid if is_running else None,
        "exitCode": poll_result if not is_running else None
    }


@app.get("/start_tensorboard")
async def start_tensorboard():
    return initialize_tensorboard()


@app.get("/get_tensorboard_url")
async def get_tensorboard_url():
    return get_tensorboard()


@app.post("/start_model_inference")
async def start_model_inference(req: Request):
    req = await req.json()
    print("start model inference")
    # log_dir = req["log_dir"]
    start_inference(req)


@app.post("/stop_model_inference")
async def stop_model_inference():
    print("Stop model inference")
    return stop_inference()


def run():
    print("\n" + "="*80)
    print("SERVER_PYTC: Starting Uvicorn server on port 4243...")
    print("="*80 + "\n")
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=4243,
        reload=False,
        log_level="info",
    )


if __name__ == "__main__":
    run()
