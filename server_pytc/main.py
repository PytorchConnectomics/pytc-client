import logging
import time
import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from app_event_logger import append_app_event, configure_process_logging
from runtime_settings import get_allowed_origins
from server_pytc.services.model import (
    get_inference_status,
    get_inference_logs,
    get_tensorboard,
    get_tensorboard_status,
    initialize_tensorboard,
    get_training_logs as get_training_process_logs,
    get_training_status as get_training_process_status,
    start_inference,
    start_training,
    stop_inference,
    stop_training,
)

app = FastAPI()
logger = logging.getLogger(__name__)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_allowed_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def configure_app_event_logging():
    log_path = configure_process_logging("server_pytc")
    logger.info("App event logging enabled at %s", log_path)


@app.middleware("http")
async def log_http_requests(request: Request, call_next):
    start_time = time.perf_counter()
    path = request.url.path
    method = request.method
    client_host = request.client.host if request.client else None
    append_app_event(
        component="server_pytc",
        event="http_request_started",
        level="INFO",
        message=f"{method} {path}",
        method=method,
        path=path,
        client_host=client_host,
    )
    try:
        response = await call_next(request)
    except Exception as exc:
        append_app_event(
            component="server_pytc",
            event="http_request_failed",
            level="ERROR",
            message=f"{method} {path} failed",
            method=method,
            path=path,
            client_host=client_host,
            latency_ms=round((time.perf_counter() - start_time) * 1000, 2),
            error_type=exc.__class__.__name__,
            error=str(exc),
        )
        raise

    append_app_event(
        component="server_pytc",
        event="http_request_completed",
        level="INFO",
        message=f"{method} {path} -> {response.status_code}",
        method=method,
        path=path,
        client_host=client_host,
        status_code=response.status_code,
        latency_ms=round((time.perf_counter() - start_time) * 1000, 2),
    )
    return response


@app.get("/hello")
def hello():
    return {"hello"}


@app.post("/start_model_training")
async def start_model_training(req: Request):
    print("\n========== SERVER_PYTC: START_MODEL_TRAINING ENDPOINT CALLED ==========")
    req = await req.json()
    append_app_event(
        component="server_pytc",
        event="training_request_received",
        level="INFO",
        message="Training request received by worker",
        source="worker_endpoint",
        payload_keys=sorted(req.keys()),
        config_origin_path=req.get("configOriginPath"),
        output_path=req.get("outputPath"),
        log_path=req.get("logPath"),
        training_config_length=len(req.get("trainingConfig") or ""),
        workflow_id=req.get("workflow_id") or req.get("workflowId"),
    )
    print(f"[SERVER_PYTC] Received request payload keys: {list(req.keys())}")
    print(f"[SERVER_PYTC] Arguments: {req.get('arguments', {})}")
    print(f"[SERVER_PYTC] Log path: {req.get('logPath', 'NOT PROVIDED')}")
    print(
        f"[SERVER_PYTC] Training config preview: {req.get('trainingConfig', '')[:200]}..."
    )

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
        print(
            "========== SERVER_PYTC: END OF START_MODEL_TRAINING (WITH ERROR) ==========\n"
        )
        raise


@app.post("/stop_model_training")
async def stop_model_training():
    print("Stop model training")
    return stop_training()


@app.get("/training_status")
async def get_training_status():
    return get_training_process_status()


@app.get("/training_logs")
async def training_logs():
    return get_training_process_logs()


@app.get("/start_tensorboard")
async def start_tensorboard(logPath: str | None = None):
    try:
        status = initialize_tensorboard(logPath)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "status": status["phase"],
        "url": get_tensorboard(),
        "tensorboard": status,
    }


@app.get("/get_tensorboard_url")
async def get_tensorboard_url():
    return get_tensorboard()


@app.get("/get_tensorboard_status")
async def tensorboard_status():
    return get_tensorboard_status()


@app.post("/start_model_inference")
async def start_model_inference(req: Request):
    req = await req.json()
    append_app_event(
        component="server_pytc",
        event="inference_request_received",
        level="INFO",
        message="Inference request received by worker",
        source="worker_endpoint",
        payload_keys=sorted(req.keys()),
        config_origin_path=req.get("configOriginPath"),
        output_path=req.get("outputPath"),
        checkpoint_path=req.get("checkpointPath")
        or (req.get("arguments") or {}).get("checkpoint"),
        inference_config_length=len(req.get("inferenceConfig") or ""),
        workflow_id=req.get("workflow_id") or req.get("workflowId"),
    )
    print("start model inference")
    return start_inference(req)


@app.post("/stop_model_inference")
async def stop_model_inference():
    print("Stop model inference")
    return stop_inference()


@app.get("/inference_status")
async def inference_status():
    return get_inference_status()


@app.get("/inference_logs")
async def inference_logs():
    return get_inference_logs()


def run():
    log_path = configure_process_logging("server_pytc")
    print("\n" + "=" * 80)
    print("SERVER_PYTC STARTING UP")
    print(f"Python executable: {__import__('sys').executable}")
    print(f"Working directory: {__import__('os').getcwd()}")
    print(f"App event log: {log_path}")
    print("=" * 80 + "\n")
    print("\n" + "=" * 80)
    print("SERVER_PYTC: Starting Uvicorn server on port 4243...")
    print("=" * 80 + "\n")
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=4243,
        reload=False,
        log_level="info",
    )


if __name__ == "__main__":
    run()
