import inspect as py_inspect
import json
import logging
import math
import os
import pathlib
import re
import shutil
import tempfile
import threading
import traceback
import time
import uuid
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from datetime import datetime, timezone
from typing import Any, List, Optional
from urllib.parse import urlsplit, urlunsplit

import requests
import uvicorn
from fastapi import Depends, FastAPI, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import inspect, text
from sqlalchemy.orm import Session
from app_event_logger import (
    append_app_event,
    configure_process_logging,
    get_app_event_log_path,
)
from runtime_settings import (
    get_allowed_origins,
    get_neuroglancer_public_base,
)
from server_api.utils.io import readVol
from server_api.utils.utils import process_path
from server_api.auth import models, database, router as auth_router
from server_api.auth.database import get_db
from server_api.auth.router import get_current_user
from server_api.ehtool import router as ehtool_router
from server_api.chatbot.logging_utils import (
    log_request_summary,
    request_id_from_request,
)
from server_api.workflows import router as workflow_router
from server_api.workflows.db_models import WorkflowCommand, WorkflowEvent
from server_api.workflows.service import (
    append_event_for_workflow_if_present,
    command_to_dict,
    decode_json,
    fail_workflow_command,
    get_user_workflow_or_404,
    mark_workflow_command_running,
    submit_workflow_command,
    update_workflow_fields,
)
from server_api.workflows.volume_io import load_volume
from server_api.workflows.volume_pairs import (
    _is_chunked_volume_directory,
    _is_neuroglancer_volume_file,
    _path_has_suffix,
    _resolve_neuroglancer_image_path,
    _resolve_neuroglancer_label_path,
    _volume_file_candidates,
    _volume_pair_key,
    discover_neuroglancer_volume_pairs,
    NEUROGLANCER_VOLUME_DIR_SUFFIXES,
    NEUROGLANCER_VOLUME_FILE_SUFFIXES,
)

from fastapi.staticfiles import StaticFiles
import os

# Chatbot is optional; keep the server running if dependencies or model endpoints
# are unavailable. We initialize lazily on demand.
try:
    from server_api.chatbot.chatbot import (
        build_chain,
        build_helper_chain,
        _compact_agent_response,
        _format_admin_llm_error,
        _sanitize_agent_response,
    )
except Exception as exc:  # pragma: no cover - exercised indirectly via endpoints
    build_chain = None
    build_helper_chain = None
    _chatbot_error = exc

    def _format_admin_llm_error(error):
        return (
            "The AI assistant could not connect to its configured language model. "
            "Please contact your system administrator with this error: "
            f"{str(error).strip() or error.__class__.__name__}"
        )

    def _compact_agent_response(response, max_words=120):
        return str(response or "")

    def _sanitize_agent_response(response):
        return str(response or "").strip()

else:
    _chatbot_error = None

chain = None
_reset_search = None

# In-memory LangChain history, keyed by conversation ID for the main chatbot.
# Rebuilt from DB when switching conversations.
_active_convo_id: Optional[int] = None
_chat_history: list = []

# Helper chat (inline "?" popovers) — keyed by taskKey for isolated sessions
_helper_chains = {}  # taskKey -> (agent, reset_fn)
_helper_histories = {}  # taskKey -> list of messages
_SHARED_HELPER_CHAIN_KEY = "__shared_inline_helper__"


def _ensure_chatbot():
    global chain, _reset_search, _chatbot_error
    if chain is not None and _reset_search is not None:
        print("[CHATBOT] Reusing initialized main chat chain")
        return True
    if build_chain is None:
        print("[CHATBOT] build_chain is unavailable; chatbot backend not configured")
        return False
    start_time = time.perf_counter()
    print("[CHATBOT] Initializing main chat chain...")
    try:
        chain, _reset_search = build_chain()
        _chatbot_error = None
        elapsed = time.perf_counter() - start_time
        print(f"[CHATBOT] Main chat chain ready in {elapsed:.2f}s")
        return True
    except Exception as exc:  # pragma: no cover - runtime config issue
        chain = None
        _reset_search = None
        _chatbot_error = exc
        print(
            "[CHATBOT] Failed to initialize LLM backend: "
            f"{exc.__class__.__name__}: {exc!r}"
        )
        traceback.print_exc()
        return False


def _llm_unavailable_detail(error):
    return {
        "user_message": _format_admin_llm_error(error),
        "error": str(error),
        "reason": "llm_unavailable",
    }


def _llm_unavailable_chat_response() -> str:
    return (
        "I cannot reach the documentation assistant right now.\n"
        "Do this: use the workflow actions I can still inspect: status, show data, "
        "run model, proofread, train, compare results, or move screens.\n"
        "Watch out: documentation search may be incomplete until the local Ollama "
        "models are configured."
    )


def _invoke_with_progress(invoke_fn, *, label: str, request_id: str, poll_seconds=5.0):
    start_time = time.perf_counter()
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(invoke_fn)
        while True:
            try:
                result = future.result(timeout=poll_seconds)
                elapsed = time.perf_counter() - start_time
                print(f"[CHATBOT][{request_id}] {label} completed in {elapsed:.2f}s")
                return result
            except TimeoutError:
                elapsed = time.perf_counter() - start_time
                print(
                    f"[CHATBOT][{request_id}] {label} still running "
                    f"after {elapsed:.2f}s..."
                )


def _env_int(name: str, default: int) -> int:
    raw_value = os.getenv(name)
    if raw_value is None or raw_value == "":
        return default
    try:
        return int(raw_value)
    except ValueError as exc:
        raise RuntimeError(f"{name} must be an integer, got {raw_value!r}") from exc


REACT_APP_SERVER_PROTOCOL = os.getenv("PYTC_WORKER_PROTOCOL", "http")
REACT_APP_SERVER_URL = os.getenv("PYTC_WORKER_URL", "localhost:4243")
PYTC_API_HOST = os.getenv("PYTC_API_HOST", "0.0.0.0")
PYTC_API_PORT = _env_int("PYTC_API_PORT", 4242)
PYTC_NEUROGLANCER_BIND_HOST = os.getenv("PYTC_NEUROGLANCER_BIND_HOST", "0.0.0.0")
PYTC_NEUROGLANCER_PORT = _env_int("PYTC_NEUROGLANCER_PORT", 4244)
PYTC_NEUROGLANCER_VIEWER_TTL_SECONDS = _env_int(
    "PYTC_NEUROGLANCER_VIEWER_TTL_SECONDS",
    2 * 60 * 60,
)
PYTC_NEUROGLANCER_MAX_VIEWERS = _env_int("PYTC_NEUROGLANCER_MAX_VIEWERS", 12)

_retained_neuroglancer_viewers = OrderedDict()
_retained_neuroglancer_viewers_lock = threading.RLock()

models.Base.metadata.create_all(bind=database.engine)


def _ensure_sqlite_column(table_name: str, column_name: str, ddl: str) -> None:
    if database.engine.dialect.name != "sqlite":
        return
    inspector = inspect(database.engine)
    if table_name not in inspector.get_table_names():
        return
    existing = {column["name"] for column in inspector.get_columns(table_name)}
    if column_name in existing:
        return
    with database.engine.begin() as connection:
        connection.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {ddl}"))


_ensure_sqlite_column("ehtool_sessions", "workflow_id", "workflow_id INTEGER")
_ensure_sqlite_column("chat_messages", "source", "source VARCHAR")
_ensure_sqlite_column("chat_messages", "workflow_id", "workflow_id INTEGER")
_ensure_sqlite_column("chat_messages", "actions_json", "actions_json TEXT")
_ensure_sqlite_column("chat_messages", "commands_json", "commands_json TEXT")
_ensure_sqlite_column("chat_messages", "proposals_json", "proposals_json TEXT")
_ensure_sqlite_column("chat_messages", "trace_json", "trace_json TEXT")
_ensure_sqlite_column("workflow_sessions", "config_path", "config_path VARCHAR")
_ensure_sqlite_column(
    "workflow_events", "schema_version", "schema_version INTEGER DEFAULT 1 NOT NULL"
)
_ensure_sqlite_column("workflow_events", "idempotency_key", "idempotency_key VARCHAR")
_ensure_sqlite_column("workflow_model_runs", "run_id", "run_id VARCHAR")
_ensure_sqlite_column(
    "workflow_volume_states", "annotation_state", "annotation_state VARCHAR"
)
_ensure_sqlite_column("workflow_volume_states", "role_state", "role_state VARCHAR")
_ensure_sqlite_column(
    "workflow_volume_states", "execution_state", "execution_state VARCHAR"
)
_ensure_sqlite_column(
    "workflow_volume_states", "region_scope_json", "region_scope_json TEXT"
)
_ensure_sqlite_column(
    "workflow_volume_states", "state_schema_version", "state_schema_version VARCHAR"
)

app = FastAPI()

# Ensure uploads directory exists
os.makedirs("uploads", exist_ok=True)
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

app.include_router(auth_router.router)
app.include_router(ehtool_router.router, prefix="/eh", tags=["ehtool"])
app.include_router(workflow_router.router, prefix="/api/workflows", tags=["workflows"])

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_allowed_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

logger = logging.getLogger(__name__)


UM_NEUROGLANCER_RAW_IMAGE_SHADER = """#uicontrol invlerp normalized
#uicontrol float brightness slider(min=-1, max=1)
#uicontrol float contrast slider(min=-3, max=3, step=0.01)

void main() {
  emitGrayscale((normalized() + brightness) * exp(contrast));
}
"""

UM_NEUROGLANCER_MASK_RED_SHADER = """void main() {
  emitRGB(vec3(1.0, 0.0, 0.0));
}
"""


def _has_single_neuroglancer_main(shader: str) -> bool:
    return len(re.findall(r"\bvoid\s+main\s*\(", shader)) == 1


def _resolve_raw_image_shader() -> str:
    # Applied to raw image layers by default for the UM/Yixiao Neuroglancer view.
    # This is intentionally shared for all raw image layers unless this helper is
    # tightened later for a narrower demo scope.
    return UM_NEUROGLANCER_RAW_IMAGE_SHADER


def _resolve_mask_image_shader() -> str:
    # Red mask/prediction image-layer shader. Segmentation layers use
    # dedicated segmentation rendering instead and should not receive this shader.
    return UM_NEUROGLANCER_MASK_RED_SHADER


def _with_neuroglancer_image_shader(
    neuroglancer_module,
    layer_source,
    shader: str,
):
    image_layer = getattr(neuroglancer_module, "ImageLayer", None)
    if image_layer is None:
        try:
            layer_source.shader = shader
        except Exception:
            logger.debug("Unable to attach Neuroglancer image shader directly.", exc_info=True)
        return layer_source

    try:
        image_init_signature = py_inspect.signature(image_layer.__init__)
        if "shader" in image_init_signature.parameters:
            return image_layer(source=layer_source, shader=shader)
    except Exception:
        logger.debug("Unable to probe Neuroglancer ImageLayer __init__ signature.", exc_info=True)

    try:
        return image_layer(source=layer_source, shader=shader)
    except TypeError:
        try:
            layer_source.shader = shader
        except Exception:
            logger.debug("Unable to apply Neuroglancer image shader to layer source.", exc_info=True)
    return layer_source


def _build_neuroglancer_local_volume_source(
    neuroglancer_module,
    data,
    dimensions,
    *,
    volume_type: str = "image",
    voxel_offset=(0, 0, 0),
):
    return neuroglancer_module.LocalVolume(
        data,
        dimensions=dimensions,
        volume_type=volume_type,
        voxel_offset=voxel_offset,
    )


def _build_neuroglancer_layer(
    neuroglancer_module,
    data,
    dimensions,
    *,
    volume_type: str = "image",
    voxel_offset=(0, 0, 0),
    image_shader: Optional[str] = None,
    segmentation_kwargs: Optional[dict[str, Any]] = None,
):
    source = _build_neuroglancer_local_volume_source(
        neuroglancer_module,
        data,
        dimensions,
        volume_type=volume_type,
        voxel_offset=voxel_offset,
    )
    if volume_type == "segmentation":
        if segmentation_kwargs is None:
            return neuroglancer_module.SegmentationLayer(source=source)
        return neuroglancer_module.SegmentationLayer(source=source, **segmentation_kwargs)
    shader = image_shader or _resolve_raw_image_shader()
    return _with_neuroglancer_image_shader(neuroglancer_module, source, shader)


class ClientAppLogEvent(BaseModel):
    event: str
    level: str = "INFO"
    message: Optional[str] = None
    source: Optional[str] = None
    sessionId: Optional[str] = None
    url: Optional[str] = None
    data: Optional[dict[str, Any]] = None


class WorkflowInferenceRuntimeSyncRequest(BaseModel):
    stage: Optional[str] = None


class NeuroglancerProofreadRequest(BaseModel):
    image: Optional[str] = None
    label: Optional[str] = None
    scales: Optional[List[float]] = None
    workflow_id: Optional[int] = None
    workflowId: Optional[int] = None
    session_id: Optional[int] = None
    sessionId: Optional[int] = None
    active_instance_id: Optional[int] = None
    activeInstanceId: Optional[int] = None
    initial_voxel: Optional[List[float]] = None
    initialVoxel: Optional[List[float]] = None


_PREDICTION_OUTPUT_SUFFIXES = (
    ".h5",
    ".hdf5",
    ".hdf",
    ".tif",
    ".tiff",
    ".ome.tif",
    ".ome.tiff",
    ".zarr",
    ".n5",
    ".npy",
    ".npz",
    ".nii",
    ".nii.gz",
    ".mrc",
    ".map",
    ".rec",
)


def _path_has_prediction_suffix(path: pathlib.Path) -> bool:
    lower_name = path.name.lower()
    lower_path = str(path).lower()
    return lower_name.endswith(_PREDICTION_OUTPUT_SUFFIXES) or lower_path.endswith(
        (".ome.tif", ".ome.tiff", ".nii.gz")
    )


def _is_prediction_output_candidate(path: pathlib.Path) -> bool:
    if path.name.startswith("."):
        return False
    if not _path_has_prediction_suffix(path):
        return False
    if path.is_dir():
        return path.name.lower().endswith((".zarr", ".n5"))
    return path.is_file()


def _prediction_output_priority(path: pathlib.Path) -> tuple[float, int, str]:
    name = path.name.lower()
    preferred = 0
    if name.startswith("result_xy"):
        preferred = 3
    elif name.startswith("result"):
        preferred = 2
    elif "prediction" in name or "pred" in name:
        preferred = 1
    try:
        mtime = path.stat().st_mtime
    except OSError:
        mtime = 0.0
    return (mtime, preferred, path.name)


def _discover_prediction_output(path_value: Optional[str]) -> Optional[str]:
    if not path_value or not str(path_value).strip():
        return None

    candidate = pathlib.Path(str(path_value).strip()).expanduser()
    if not candidate.is_absolute():
        candidate = (pathlib.Path.cwd() / candidate).resolve()
    else:
        candidate = candidate.resolve()
    if _is_prediction_output_candidate(candidate):
        return str(candidate)

    if candidate.is_dir():
        output_dir = candidate
    elif candidate.parent.exists():
        output_dir = candidate.parent
    else:
        return None

    candidates = [
        child
        for child in output_dir.rglob("*")
        if _is_prediction_output_candidate(child)
    ]
    if not candidates:
        return None
    return str(max(candidates, key=_prediction_output_priority).resolve())


def _metadata_path(metadata: dict[str, Any], *keys: str) -> Optional[str]:
    for key in keys:
        value = metadata.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return None


def _find_synced_inference_event(
    db: Session,
    *,
    workflow_id: int,
    event_type: str,
    output_path: Optional[str] = None,
    ended_at: Optional[str] = None,
) -> Optional[WorkflowEvent]:
    events = (
        db.query(WorkflowEvent)
        .filter(
            WorkflowEvent.workflow_id == workflow_id,
            WorkflowEvent.event_type == event_type,
        )
        .order_by(WorkflowEvent.id.desc())
        .all()
    )
    for event in events:
        payload = decode_json(event.payload_json)
        if payload.get("source") != "runtime_sync":
            continue
        if output_path and payload.get("outputPath") == output_path:
            return event
        if ended_at and payload.get("runtimeEndedAt") == ended_at:
            return event
    return None


def _resolve_existing_runtime_path(path_value: Any) -> Optional[str]:
    if not isinstance(path_value, str) or not path_value.strip():
        return None
    candidate = pathlib.Path(path_value).expanduser()
    if not candidate.is_absolute():
        candidate = pathlib.Path(process_path(path_value))
    if candidate.exists():
        return str(candidate.resolve())
    return None


def _require_runtime_path(path_value: Any, role: str) -> str:
    resolved = _resolve_existing_runtime_path(path_value)
    if resolved:
        return resolved
    raise HTTPException(
        status_code=400,
        detail=f"{role} path does not exist: {path_value or '<empty>'}",
    )


def _first_existing_runtime_path(role: str, *path_values: Any) -> str:
    first_requested = None
    for path_value in path_values:
        if not isinstance(path_value, str) or not path_value.strip():
            continue
        if first_requested is None:
            first_requested = path_value
        resolved = _resolve_existing_runtime_path(path_value)
        if resolved:
            return resolved
    raise HTTPException(
        status_code=400,
        detail=f"{role} path does not exist: {first_requested or '<empty>'}",
    )


def _runtime_body_with_workflow_fallbacks(
    body: dict[str, Any],
    workflow,
    *,
    mode: str,
) -> dict[str, Any]:
    next_body = dict(body)
    metadata = decode_json(getattr(workflow, "metadata_json", None))
    if mode == "training":
        next_body["inputImagePath"] = _first_existing_runtime_path(
            "Training image",
            next_body.get("inputImagePath"),
            workflow.image_path,
            metadata.get("image_path"),
            metadata.get("image"),
            metadata.get("imageDataPath"),
            metadata.get("inputImagePath"),
        )
        next_body["inputLabelPath"] = _first_existing_runtime_path(
            "Training label",
            next_body.get("inputLabelPath"),
            workflow.corrected_mask_path,
            workflow.label_path,
            workflow.mask_path,
            metadata.get("corrected_mask_path"),
            metadata.get("label_path"),
            metadata.get("mask_path"),
            metadata.get("inputLabelPath"),
        )
        return next_body

    if mode == "inference":
        next_body["inputImagePath"] = _first_existing_runtime_path(
            "Inference image",
            next_body.get("inputImagePath"),
            workflow.image_path,
            metadata.get("image_path"),
            metadata.get("image"),
            metadata.get("imageDataPath"),
            metadata.get("inputImagePath"),
        )
        checkpoint = (
            (next_body.get("arguments") or {}).get("checkpoint")
            or next_body.get("checkpointPath")
        )
        checkpoint = _first_existing_runtime_path(
            "Checkpoint",
            checkpoint,
            workflow.checkpoint_path,
            metadata.get("checkpoint_path"),
            metadata.get("checkpointPath"),
        )
        arguments = dict(next_body.get("arguments") or {})
        arguments["checkpoint"] = checkpoint
        next_body["arguments"] = arguments
        next_body["checkpointPath"] = checkpoint
        return next_body

    return next_body


def _first_string(*values: Any) -> Optional[str]:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _build_training_body_from_command(
    command: WorkflowCommand,
    workflow,
) -> dict[str, Any]:
    command_input = decode_json(command.input_json)
    client_effects = command_input.get("client_effects")
    if not isinstance(client_effects, dict):
        client_effects = {}
    runtime_action = client_effects.get("runtime_action")
    if not isinstance(runtime_action, dict):
        runtime_action = {}

    config_origin_path = _first_string(
        command_input.get("configOriginPath"),
        command_input.get("config_origin_path"),
        command_input.get("config_preset"),
        client_effects.get("set_training_config_preset"),
        workflow.config_path,
    )
    training_config = _first_string(
        command_input.get("trainingConfig"),
        command_input.get("training_config"),
    )
    if not training_config:
        if not config_origin_path:
            raise HTTPException(
                status_code=400,
                detail="Training command is missing a config preset or config text.",
            )
        config_origin_path, training_config = _read_pytc_config_content(config_origin_path)

    output_path = _first_string(
        command_input.get("outputPath"),
        command_input.get("output_path"),
        client_effects.get("set_training_output_path"),
        workflow.training_output_path,
    )
    if not output_path:
        raise HTTPException(
            status_code=400,
            detail="Training command is missing an output path.",
        )

    label_path = _first_string(
        command_input.get("inputLabelPath"),
        command_input.get("label_path"),
        client_effects.get("set_training_label_path"),
        workflow.corrected_mask_path,
        workflow.label_path,
        workflow.mask_path,
    )
    image_path = _first_string(
        command_input.get("inputImagePath"),
        command_input.get("image_path"),
        client_effects.get("set_training_image_path"),
        workflow.image_path,
    )
    log_path = _first_string(
        command_input.get("logPath"),
        command_input.get("log_path"),
        client_effects.get("set_training_log_path"),
        output_path,
    )
    run_id = _first_string(
        command_input.get("run_id"),
        command_input.get("runId"),
        f"workflow-command-{command.id}",
    )

    return {
        "trainingConfig": training_config,
        "configOriginPath": config_origin_path,
        "outputPath": output_path,
        "logPath": log_path,
        "inputImagePath": image_path,
        "inputLabelPath": label_path,
        "workflowId": workflow.id,
        "workflow_id": workflow.id,
        "command_id": command.id,
        "run_id": run_id,
        "autoParameters": bool(
            command_input.get("autoParameters")
            or command_input.get("auto_parameters")
            or command_input.get("autopick_parameters")
            or runtime_action.get("autopick_parameters")
        ),
    }


@app.on_event("startup")
async def configure_app_event_logging():
    log_path = configure_process_logging("server_api")
    logger.info("App event logging enabled at %s", log_path)
    append_app_event(
        component="server_api",
        event="api_runtime_configured",
        level="INFO",
        message="API runtime configuration loaded.",
        api_host=PYTC_API_HOST,
        api_port=PYTC_API_PORT,
        worker_protocol=REACT_APP_SERVER_PROTOCOL,
        worker_url=REACT_APP_SERVER_URL,
        neuroglancer_port=PYTC_NEUROGLANCER_PORT,
        neuroglancer_public_base=get_neuroglancer_public_base(),
        log_path=str(log_path),
    )


def _normalize_api_compat_path(path: str) -> Optional[str]:
    if path.startswith("/api/api/"):
        return "/api/" + path[len("/api/api/") :]
    if path == "/api/files":
        return "/files"
    if path.startswith("/api/files/"):
        return "/files/" + path[len("/api/files/") :]
    if path.startswith("/api/app/"):
        return "/app/" + path[len("/api/app/") :]
    if path == "/api/neuroglancer":
        return "/neuroglancer"
    if path.startswith("/api/neuroglancer/"):
        return "/neuroglancer/" + path[len("/api/neuroglancer/") :]
    if path.startswith("/api/start_model_"):
        return path[len("/api") :]
    if path.startswith("/api/stop_model_"):
        return path[len("/api") :]
    if path in {
        "/api/training_status",
        "/api/training_logs",
        "/api/inference_status",
        "/api/inference_logs",
        "/api/start_tensorboard",
        "/api/get_tensorboard_url",
        "/api/get_tensorboard_status",
    }:
        return path[len("/api") :]
    return None


@app.middleware("http")
async def log_http_requests(request: Request, call_next):
    request_id = request_id_from_request(request)
    start_time = time.perf_counter()
    path = request.url.path
    normalized_path = _normalize_api_compat_path(path)
    if normalized_path:
        request.scope["path"] = normalized_path
        request.scope["raw_path"] = normalized_path.encode("utf-8")
        path = normalized_path
    method = request.method
    client_host = request.client.host if request.client else None
    is_client_log_endpoint = path == "/app/log-event"
    if not is_client_log_endpoint:
        append_app_event(
            component="server_api",
            event="http_request_started",
            level="INFO",
            message=f"{method} {path}",
            request_id=request_id,
            method=method,
            path=path,
            query=str(request.url.query or ""),
            client_host=client_host,
        )
    try:
        response = await call_next(request)
    except Exception as exc:
        append_app_event(
            component="server_api",
            event="http_request_failed",
            level="ERROR",
            message=f"{method} {path} failed",
            request_id=request_id,
            method=method,
            path=path,
            client_host=client_host,
            latency_ms=round((time.perf_counter() - start_time) * 1000, 2),
            error_type=exc.__class__.__name__,
            error=str(exc),
        )
        raise

    response.headers.setdefault("x-request-id", request_id)
    latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
    if not is_client_log_endpoint or response.status_code >= 400 or latency_ms >= 1000:
        append_app_event(
            component="server_api",
            event="http_request_completed",
            level="INFO",
            message=f"{method} {path} -> {response.status_code}",
            request_id=request_id,
            method=method,
            path=path,
            client_host=client_host,
            status_code=response.status_code,
            latency_ms=latency_ms,
        )
    return response


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/app/log-path")
def app_log_path():
    return {"path": str(get_app_event_log_path())}


@app.post("/app/log-event")
async def app_log_event(payload: ClientAppLogEvent, request: Request):
    request_id = request_id_from_request(request)
    append_app_event(
        component="client",
        event=payload.event,
        level=payload.level,
        message=payload.message,
        source=payload.source,
        session_id=payload.sessionId,
        url=payload.url,
        data=payload.data or {},
        request_id=request_id,
        client_host=request.client.host if request.client else None,
    )
    return {"status": "ok"}


def _worker_url(path: str) -> str:
    return f"{REACT_APP_SERVER_PROTOCOL}://{REACT_APP_SERVER_URL}{path}"


def _derive_neuroglancer_public_base(request: Request) -> str:
    configured_base = get_neuroglancer_public_base()
    if configured_base:
        return configured_base

    forwarded_proto = request.headers.get("x-forwarded-proto")
    scheme = (forwarded_proto.split(",")[0].strip() if forwarded_proto else "") or (
        request.url.scheme or "http"
    )

    forwarded_host = request.headers.get("x-forwarded-host")
    request_host = (
        forwarded_host.split(",")[0].strip() if forwarded_host else request.url.netloc
    )
    hostname = request_host.split(":")[0] or "localhost"
    return f"{scheme}://{hostname}:{PYTC_NEUROGLANCER_PORT}"


def _build_neuroglancer_public_url(viewer_url: str, request: Request) -> str:
    viewer_parts = urlsplit(viewer_url)
    base_parts = urlsplit(_derive_neuroglancer_public_base(request))
    base_path = base_parts.path.rstrip("/")
    viewer_path = viewer_parts.path or ""
    combined_path = f"{base_path}{viewer_path}" if base_path else viewer_path

    return urlunsplit(
        (
            base_parts.scheme or "http",
            base_parts.netloc,
            combined_path,
            viewer_parts.query,
            viewer_parts.fragment,
        )
    )


def _neuroglancer_token_from_url(viewer_url: str) -> Optional[str]:
    path_parts = [part for part in urlsplit(viewer_url).path.split("/") if part]
    if len(path_parts) >= 2 and path_parts[-2] == "v":
        return path_parts[-1]
    return None


def _cleanup_retained_neuroglancer_viewers(now: Optional[float] = None):
    if now is None:
        now = time.time()
    evicted = []
    ttl_seconds = max(PYTC_NEUROGLANCER_VIEWER_TTL_SECONDS, 0)

    if ttl_seconds:
        for token, entry in list(_retained_neuroglancer_viewers.items()):
            if now - entry["created_at"] > ttl_seconds:
                evicted.append(
                    {
                        "token": token,
                        "reason": "ttl",
                        "age_seconds": round(now - entry["created_at"], 3),
                        "mode": entry.get("mode"),
                    }
                )
                _retained_neuroglancer_viewers.pop(token, None)

    max_viewers = max(PYTC_NEUROGLANCER_MAX_VIEWERS, 0)
    while max_viewers and len(_retained_neuroglancer_viewers) > max_viewers:
        token, entry = _retained_neuroglancer_viewers.popitem(last=False)
        evicted.append(
            {
                "token": token,
                "reason": "capacity",
                "age_seconds": round(now - entry["created_at"], 3),
                "mode": entry.get("mode"),
            }
        )

    return evicted


def _retain_neuroglancer_viewer(
    viewer,
    *,
    public_url: str,
    internal_viewer_url: str,
    mode: str,
    workflow_id: Optional[int] = None,
    image_path: Optional[str] = None,
    label_path: Optional[str] = None,
) -> Optional[str]:
    token = getattr(viewer, "token", None) or _neuroglancer_token_from_url(
        internal_viewer_url
    )
    if not token:
        append_app_event(
            component="server_api",
            event="neuroglancer_viewer_retain_failed",
            level="ERROR",
            message="Could not retain Neuroglancer viewer because no token was found.",
            public_url=public_url,
            internal_viewer_url=internal_viewer_url,
            workflow_id=workflow_id,
            mode=mode,
        )
        return None

    now = time.time()
    with _retained_neuroglancer_viewers_lock:
        if PYTC_NEUROGLANCER_MAX_VIEWERS <= 0:
            _retained_neuroglancer_viewers.clear()
            append_app_event(
                component="server_api",
                event="neuroglancer_viewer_retention_disabled",
                level="ERROR",
                message="Neuroglancer viewer retention is disabled; returned viewer URLs may expire immediately.",
                viewer_token=token,
                public_url=public_url,
                workflow_id=workflow_id,
                mode=mode,
            )
            return token

        evicted = _cleanup_retained_neuroglancer_viewers(now)
        _retained_neuroglancer_viewers[token] = {
            "viewer": viewer,
            "public_url": public_url,
            "internal_viewer_url": internal_viewer_url,
            "mode": mode,
            "workflow_id": workflow_id,
            "image_path": image_path,
            "label_path": label_path,
            "created_at": now,
        }
        _retained_neuroglancer_viewers.move_to_end(token)
        evicted.extend(_cleanup_retained_neuroglancer_viewers(now))
        retained_count = len(_retained_neuroglancer_viewers)

    append_app_event(
        component="server_api",
        event="neuroglancer_viewer_retained",
        message="Retained live Neuroglancer viewer for iframe access.",
        viewer_token=token,
        public_url=public_url,
        internal_viewer_url=internal_viewer_url,
        workflow_id=workflow_id,
        mode=mode,
        image_path=image_path,
        label_path=label_path,
        retained_count=retained_count,
        max_viewers=PYTC_NEUROGLANCER_MAX_VIEWERS,
        ttl_seconds=PYTC_NEUROGLANCER_VIEWER_TTL_SECONDS,
        evicted=evicted,
    )
    return token


def _extract_upstream_payload(response: requests.Response):
    try:
        return response.json()
    except ValueError:
        text = (response.text or "").strip()
        return text or None


def _proxy_to_worker(
    method: str,
    path: str,
    *,
    json_body: Optional[dict] = None,
    params: Optional[dict] = None,
    timeout: int = 30,
):
    target_url = _worker_url(path)
    start_time = time.perf_counter()
    method_upper = method.upper()
    append_app_event(
        component="server_api",
        event="worker_proxy_request_started",
        level="INFO",
        message=f"{method_upper} {path} -> PyTC worker",
        method=method_upper,
        path=path,
        worker_url=target_url,
        timeout_seconds=timeout,
        has_json_body=bool(json_body),
        json_keys=sorted(json_body.keys()) if isinstance(json_body, dict) else None,
    )
    try:
        response = requests.request(
            method=method,
            url=target_url,
            json=json_body,
            params=params,
            timeout=timeout,
        )
    except requests.exceptions.ConnectionError as exc:
        append_app_event(
            component="server_api",
            event="worker_proxy_request_failed",
            level="ERROR",
            message="Failed to connect to PyTC worker.",
            method=method_upper,
            path=path,
            worker_url=target_url,
            latency_ms=round((time.perf_counter() - start_time) * 1000, 2),
            error="ConnectionError",
            reason=str(exc),
        )
        raise HTTPException(
            status_code=503,
            detail={
                "message": "Failed to connect to PyTC worker. Is server_pytc running?",
                "worker_url": target_url,
                "error": "ConnectionError",
                "reason": str(exc),
            },
        ) from exc
    except requests.exceptions.Timeout as exc:
        append_app_event(
            component="server_api",
            event="worker_proxy_request_failed",
            level="ERROR",
            message="PyTC worker request timed out.",
            method=method_upper,
            path=path,
            worker_url=target_url,
            latency_ms=round((time.perf_counter() - start_time) * 1000, 2),
            error="Timeout",
        )
        raise HTTPException(
            status_code=504,
            detail={
                "message": "PyTC worker request timed out.",
                "worker_url": target_url,
                "error": "Timeout",
            },
        ) from exc
    except requests.RequestException as exc:
        append_app_event(
            component="server_api",
            event="worker_proxy_request_failed",
            level="ERROR",
            message="Unexpected error while calling PyTC worker.",
            method=method_upper,
            path=path,
            worker_url=target_url,
            latency_ms=round((time.perf_counter() - start_time) * 1000, 2),
            error=type(exc).__name__,
            reason=str(exc),
        )
        raise HTTPException(
            status_code=502,
            detail={
                "message": "Unexpected error while calling PyTC worker.",
                "worker_url": target_url,
                "error": type(exc).__name__,
                "reason": str(exc),
            },
        ) from exc
    except Exception as exc:
        append_app_event(
            component="server_api",
            event="worker_proxy_request_failed",
            level="ERROR",
            message="Unhandled error while calling PyTC worker.",
            method=method_upper,
            path=path,
            worker_url=target_url,
            latency_ms=round((time.perf_counter() - start_time) * 1000, 2),
            error=type(exc).__name__,
            reason=str(exc),
        )
        raise HTTPException(
            status_code=502,
            detail={
                "message": "Unhandled error while calling PyTC worker.",
                "worker_url": target_url,
                "error": type(exc).__name__,
                "reason": str(exc),
            },
        ) from exc

    payload = _extract_upstream_payload(response)
    if response.status_code >= 400:
        append_app_event(
            component="server_api",
            event="worker_proxy_request_completed",
            level="ERROR",
            message="PyTC worker returned an error.",
            method=method_upper,
            path=path,
            worker_url=target_url,
            latency_ms=round((time.perf_counter() - start_time) * 1000, 2),
            status_code=response.status_code,
            upstream_body=payload,
        )
        raise HTTPException(
            status_code=response.status_code,
            detail={
                "message": "PyTC worker returned an error.",
                "worker_url": target_url,
                "upstream_status": response.status_code,
                "upstream_body": payload,
            },
        )
    append_app_event(
        component="server_api",
        event="worker_proxy_request_completed",
        level="INFO",
        message=f"{method_upper} {path} -> PyTC worker {response.status_code}",
        method=method_upper,
        path=path,
        worker_url=target_url,
        latency_ms=round((time.perf_counter() - start_time) * 1000, 2),
        status_code=response.status_code,
    )
    return payload


BASE_DIR = pathlib.Path(__file__).resolve().parent.parent
PYTC_ROOT = BASE_DIR / "pytorch_connectomics"
PYTC_CONFIG_ROOTS = (
    PYTC_ROOT / "tutorials",
    PYTC_ROOT / "configs",
)
PYTC_CONFIG_SUFFIXES = (".yaml", ".yml")


def _iter_existing_config_roots():
    for root in PYTC_CONFIG_ROOTS:
        if root.exists() and root.is_dir():
            yield root


def _list_pytc_configs() -> List[str]:
    configs = []
    for root in _iter_existing_config_roots():
        for suffix in PYTC_CONFIG_SUFFIXES:
            for path in root.rglob(f"*{suffix}"):
                configs.append(str(path.relative_to(PYTC_ROOT)).replace("\\", "/"))
    return sorted(set(configs))


def _is_relative_to(path: pathlib.Path, root: pathlib.Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _is_valid_config_path(path: pathlib.Path) -> bool:
    if not path.is_file():
        return False
    if path.suffix.lower() not in PYTC_CONFIG_SUFFIXES:
        return False
    if not _is_relative_to(path, PYTC_ROOT.resolve()):
        return False
    return any(
        _is_relative_to(path, root.resolve()) for root in _iter_existing_config_roots()
    )


def _iter_external_config_roots():
    root_values = [
        os.getenv("PYTC_INITIAL_PROJECT_ROOT"),
        "/home/weidf/demo_data",
    ]
    configured = os.getenv("PYTC_ADDITIONAL_CONFIG_ROOTS", "")
    if configured:
        root_values.extend(
            value.strip()
            for chunk in configured.split(os.pathsep)
            for value in chunk.split(",")
            if value.strip()
        )
    seen = set()
    for value in root_values:
        if not value:
            continue
        root = pathlib.Path(value).expanduser().resolve()
        if root in seen or not root.exists() or not root.is_dir():
            continue
        seen.add(root)
        yield root


def _is_valid_external_config_path(path: pathlib.Path) -> bool:
    if not path.is_file():
        return False
    if path.suffix.lower() not in PYTC_CONFIG_SUFFIXES:
        return False
    return any(_is_relative_to(path, root) for root in _iter_external_config_roots())


def _resolve_requested_config(path: str) -> Optional[pathlib.Path]:
    if not path:
        return None

    normalized = path.replace("\\", "/").strip()
    if not normalized:
        return None
    if normalized.startswith("/"):
        candidate = pathlib.Path(normalized).expanduser().resolve()
        return candidate if _is_valid_external_config_path(candidate) else None
    if ".." in pathlib.PurePosixPath(normalized).parts:
        return None

    candidates = [(PYTC_ROOT / normalized).resolve()]
    for root in _iter_existing_config_roots():
        candidates.append((root / normalized).resolve())

    for candidate in candidates:
        if _is_valid_config_path(candidate):
            return candidate
    return None


def _config_response_path(path: pathlib.Path) -> str:
    try:
        return str(path.relative_to(PYTC_ROOT)).replace("\\", "/")
    except ValueError:
        return str(path)


def _read_model_architectures() -> List[str]:
    # Prefer the runtime model map from the installed connectomics package.
    try:
        from connectomics.model.build import MODEL_MAP

        architectures = sorted(set(MODEL_MAP.keys()))
        if architectures:
            return architectures
    except Exception:
        pass

    # Fallback: parse the static model map from source.
    pattern = re.compile(r"""['"]([^'"]+)['"]\s*:\s*[A-Za-z_][A-Za-z0-9_]*""")
    architectures = []
    build_file = PYTC_ROOT / "connectomics" / "model" / "build.py"
    if build_file.is_file():
        text = build_file.read_text(encoding="utf-8", errors="ignore")
        architectures.extend(pattern.findall(text))
    return sorted(set(architectures))


@app.get("/pytc/configs")
def list_pytc_configs():
    configs = _list_pytc_configs()
    if not configs:
        raise HTTPException(status_code=404, detail="No PyTC config presets found.")
    return {"configs": configs}


@app.get("/pytc/config")
def get_pytc_config(path: str):
    if not path:
        raise HTTPException(status_code=400, detail="Config path is required.")
    requested = _resolve_requested_config(path)
    if requested is None:
        raise HTTPException(status_code=404, detail="Config not found.")
    content = requested.read_text(encoding="utf-8", errors="ignore")
    canonical_path = _config_response_path(requested)
    return {"path": canonical_path, "content": content}


def _read_pytc_config_content(path: str) -> tuple[str, str]:
    requested = _resolve_requested_config(path)
    if requested is None:
        raise HTTPException(status_code=404, detail=f"Config not found: {path}")
    content = requested.read_text(encoding="utf-8", errors="ignore")
    canonical_path = _config_response_path(requested)
    return canonical_path, content


@app.get("/pytc/architectures")
def list_pytc_architectures():
    architectures = _read_model_architectures()
    if not architectures:
        raise HTTPException(status_code=404, detail="No model architectures found.")
    return {"architectures": architectures}


def save_upload_to_tempfile(upload: UploadFile) -> pathlib.Path:
    suffix = pathlib.Path(upload.filename or "").suffix
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        upload.file.seek(0)
        shutil.copyfileobj(upload.file, tmp)
        temp_path = pathlib.Path(tmp.name)
    return temp_path


def _is_probable_label_volume(image_array) -> bool:
    import numpy as np

    if not np.issubdtype(image_array.dtype, np.integer):
        return False

    unique_values = np.unique(image_array)
    num_unique = len(unique_values)
    if num_unique == 0:
        return False

    if num_unique == 2 and np.array_equal(unique_values, np.array([0, 1])):
        return True
    if num_unique == 2 and np.array_equal(unique_values, np.array([0, 255])):
        return True
    if num_unique < 50:
        return True

    max_value = int(unique_values[-1])
    if max_value > 255 and num_unique <= 4096:
        return True

    dtype_info = np.iinfo(image_array.dtype)
    if dtype_info.max > 255 and num_unique <= 1024:
        return True

    return False


def _smallest_unsigned_dtype_for_max(max_value: int):
    import numpy as np

    if max_value <= np.iinfo(np.uint8).max:
        return np.uint8
    if max_value <= np.iinfo(np.uint16).max:
        return np.uint16
    if max_value <= np.iinfo(np.uint32).max:
        return np.uint32
    return np.uint64


def _derive_two_channel_prediction_preview(array):
    import numpy as np

    semantic = np.asarray(array[0])
    boundary = np.asarray(array[1])

    if np.issubdtype(semantic.dtype, np.floating):
        if not np.all(np.isfinite(semantic)):
            raise ValueError("2-channel prediction foreground contains NaN or infinity.")
        foreground_threshold = 0.5 if float(np.nanmax(semantic, initial=0.0)) <= 1.0 else 127.5
        foreground = semantic > foreground_threshold
    else:
        foreground = semantic > 0

    if np.issubdtype(boundary.dtype, np.floating):
        if not np.all(np.isfinite(boundary)):
            raise ValueError("2-channel prediction boundary contains NaN or infinity.")
        boundary_threshold = 0.5 if float(np.nanmax(boundary, initial=0.0)) <= 1.0 else 127.5
        boundary_mask = boundary > boundary_threshold
    else:
        boundary_mask = boundary > 0

    foreground = foreground & ~boundary_mask
    if not np.any(foreground):
        return foreground.astype(np.uint8, copy=False)

    try:
        from scipy import ndimage

        labels, _count = ndimage.label(foreground)
    except Exception:
        labels = foreground.astype(np.uint8, copy=False)
    return labels


def _normalize_segmentation_volume_for_neuroglancer(volume):
    import numpy as np

    array = np.asarray(volume)
    if array.ndim == 4:
        if array.shape[0] <= 16:
            channel_axis = 0
        elif array.shape[-1] <= 16:
            channel_axis = -1
        else:
            raise ValueError(
                "4D label volumes must use a small channel axis to be visualized."
            )

        if channel_axis != 0:
            array = np.moveaxis(array, channel_axis, 0)

        channel_count = int(array.shape[0])
        if channel_count == 1:
            array = array[0]
        elif channel_count == 2:
            try:
                from connectomics.utils.process import bc_watershed

                array = bc_watershed(array, thres_small=1, seed_thres=1)
            except Exception as exc:
                append_app_event(
                    component="server_api",
                    event="neuroglancer_prediction_preview_fallback",
                    level="WARNING",
                    message=(
                        "Falling back to connected-component prediction preview "
                        "because connectomics bc_watershed failed."
                    ),
                    error=str(exc),
                )
                array = _derive_two_channel_prediction_preview(array)
        else:
            array = np.argmax(array, axis=0)

    if array.size == 0:
        return array.astype(np.uint8, copy=False)

    if np.issubdtype(array.dtype, np.bool_):
        return array.astype(np.uint8, copy=False)

    if np.issubdtype(array.dtype, np.floating):
        if not np.all(np.isfinite(array)):
            raise ValueError(
                "Segmentation volumes must not contain NaN or infinite values."
            )
        rounded = np.rint(array)
        if not np.allclose(array, rounded):
            raise ValueError("Segmentation volumes must use integer-valued labels.")
        array = rounded.astype(np.int64, copy=False)

    if not np.issubdtype(array.dtype, np.integer):
        raise ValueError(f"Segmentation volume dtype {array.dtype} is not supported.")

    min_value = int(array.min())
    if min_value < 0:
        raise ValueError("Segmentation volumes must contain non-negative label ids.")

    max_value = int(array.max())
    target_dtype = _smallest_unsigned_dtype_for_max(max_value)
    if array.dtype == np.dtype(target_dtype):
        return array
    return array.astype(target_dtype, copy=False)


def _raise_missing_volume_error(path: pathlib.Path, role: str) -> None:
    target = str(path)
    role_name = "image" if role == "image" else "label"
    if "/uploads/" in target or target.startswith("uploads/"):
        raise HTTPException(
            status_code=400,
            detail=(
                f"The selected {role_name} file is no longer present in app uploads. "
                f"Please re-select or re-upload it."
            ),
        )
    raise HTTPException(
        status_code=400,
        detail=f"The selected {role_name} file does not exist on disk: {target}",
    )


def _coerce_neuroglancer_scales(scales: Optional[List[float]]) -> List[float]:
    if scales is None:
        raise HTTPException(
            status_code=400,
            detail="Neuroglancer scales are required as z, y, x nanometers.",
        )
    if len(scales) != 3:
        raise HTTPException(
            status_code=400,
            detail="Neuroglancer scales must contain z, y, x values.",
        )
    try:
        coerced = [float(value) for value in scales]
    except (TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=400,
            detail="Neuroglancer scales must be numeric.",
        ) from exc
    if any(not math.isfinite(value) or value <= 0 for value in coerced):
        raise HTTPException(
            status_code=400,
            detail="Neuroglancer scales must be finite positive numbers.",
        )
    return coerced


def _coerce_initial_voxel(
    voxel: Optional[List[float]], shape: Optional[tuple[int, ...]] = None
) -> Optional[List[float]]:
    if voxel is None:
        if not shape or len(shape) < 3:
            return None
        return [
            float(max(int(shape[-3] // 2), 0)),
            float(max(int(shape[-2] // 2), 0)),
            float(max(int(shape[-1] // 2), 0)),
        ]
    if len(voxel) != 3:
        raise HTTPException(
            status_code=400,
            detail="Initial Neuroglancer voxel must contain z, y, x values.",
        )
    try:
        return [float(value) for value in voxel]
    except (TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=400,
            detail="Initial Neuroglancer voxel values must be numeric.",
        ) from exc


def _selected_segment_from_action_state(action_state, layer_names: List[str]):
    selected_values = getattr(action_state, "selected_values", None) or {}
    for layer_name in layer_names:
        selected = selected_values.get(layer_name)
        if selected is None:
            continue
        value = getattr(selected, "value", selected)
        key = getattr(value, "key", None)
        if key is not None:
            value = key
        try:
            value = int(value)
        except (TypeError, ValueError):
            continue
        if value != 0:
            return value
    return None


def _record_neuroglancer_proofread_action(
    *,
    workflow_id: Optional[int],
    action_type: str,
    payload: dict[str, Any],
) -> None:
    append_app_event(
        component="server_api",
        event="neuroglancer_proofread_action",
        message=f"Neuroglancer proofreading action: {action_type}",
        action_type=action_type,
        workflow_id=workflow_id,
        **payload,
    )
    if not workflow_id:
        return
    db = database.SessionLocal()
    try:
        append_event_for_workflow_if_present(
            db,
            workflow_id=int(workflow_id),
            actor="user",
            event_type="proofreading.neuroglancer_action",
            stage="proofreading",
            summary=f"Recorded Neuroglancer proofreading action: {action_type}.",
            payload={"action_type": action_type, **payload},
        )
    except Exception:
        logger.debug("Failed to record Neuroglancer workflow event", exc_info=True)
    finally:
        db.close()


@app.post("/neuroglancer")
async def neuroglancer(
    req: Request,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    import neuroglancer

    cleanup_paths: List[pathlib.Path] = []
    try:
        content_type = req.headers.get("content-type", "")
        if "multipart/form-data" in content_type:
            form = await req.form()
            image_upload = form.get("image")
            if not image_upload or not getattr(image_upload, "filename", None):
                raise HTTPException(status_code=400, detail="Image file is required.")
            scales_raw = form.get("scales")
            if scales_raw is None:
                raise HTTPException(status_code=400, detail="Scales are required.")
            try:
                scales = json.loads(scales_raw)
            except json.JSONDecodeError:
                raise HTTPException(
                    status_code=400, detail="Scales payload is invalid."
                )
            workflow_id_raw = form.get("workflow_id")
            workflow_id = int(workflow_id_raw) if workflow_id_raw else None

            image = save_upload_to_tempfile(image_upload)
            cleanup_paths.append(image)

            label_upload = form.get("label")
            label: Optional[pathlib.Path] = None
            if label_upload and getattr(label_upload, "filename", None):
                label = save_upload_to_tempfile(label_upload)
                cleanup_paths.append(label)
        else:
            payload = await req.json()
            image_value = (
                payload.get("image")
                or payload.get("image_path")
                or payload.get("imagePath")
            )
            if not image_value:
                raise HTTPException(
                    status_code=400, detail="Image path or file is required."
                )
            image = process_path(image_value)
            label = process_path(
                payload.get("label")
                or payload.get("label_path")
                or payload.get("labelPath")
            )
            scales = payload.get("scales")
            if scales is None:
                raise HTTPException(status_code=400, detail="Scales are required.")
            workflow_id = payload.get("workflow_id") or payload.get("workflowId")

        scales = _coerce_neuroglancer_scales(scales)
        if image is None:
            raise HTTPException(
                status_code=400, detail="Image path or file is required."
            )
        original_image_path = pathlib.Path(image)
        original_label_path = pathlib.Path(label) if label is not None else None
        if not original_image_path.exists():
            _raise_missing_volume_error(original_image_path, "image")
        if original_label_path is not None and not original_label_path.exists():
            _raise_missing_volume_error(original_label_path, "label")
        append_app_event(
            component="server_api",
            event="neuroglancer_request_prepared",
            message="Preparing Neuroglancer viewer request.",
            image_path=str(original_image_path),
            label_path=str(original_label_path) if original_label_path else None,
            scales=scales,
            workflow_id=workflow_id,
            content_type=content_type,
            request_host=req.headers.get("host"),
            forwarded_proto=req.headers.get("x-forwarded-proto"),
            forwarded_host=req.headers.get("x-forwarded-host"),
            configured_public_base=get_neuroglancer_public_base(),
        )

        pair_discovery = discover_neuroglancer_volume_pairs(
            original_image_path,
            original_label_path,
        )
        if pair_discovery["pair_count"]:
            append_app_event(
                component="server_api",
                event="neuroglancer_volume_pairs_detected",
                message="Detected image/segmentation pairs from visualization input.",
                image_path=str(original_image_path),
                label_path=str(original_label_path) if original_label_path else None,
                pair_count=pair_discovery["pair_count"],
                image_candidate_count=pair_discovery["image_candidate_count"],
                label_candidate_count=pair_discovery["label_candidate_count"],
                selected_pair=pair_discovery["pairs"][0],
            )

        try:
            resolved_image_path, image_resolution_note = _resolve_neuroglancer_image_path(
                original_image_path,
                original_label_path,
            )
            resolved_label_path, label_resolution_note = _resolve_neuroglancer_label_path(
                original_label_path,
                resolved_image_path,
            )
        except ValueError as exc:
            append_app_event(
                component="server_api",
                event="neuroglancer_volume_resolution_failed",
                level="ERROR",
                message=str(exc),
                image_path=str(original_image_path),
                label_path=str(original_label_path) if original_label_path else None,
            )
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        if image_resolution_note or label_resolution_note:
            append_app_event(
                component="server_api",
                event="neuroglancer_volume_path_resolved",
                message="Resolved folder-level visualization inputs to concrete volume files.",
                image_path=str(original_image_path),
                label_path=str(original_label_path) if original_label_path else None,
                resolved_image_path=str(resolved_image_path),
                resolved_label_path=str(resolved_label_path)
                if resolved_label_path
                else None,
                image_resolution_note=image_resolution_note,
                label_resolution_note=label_resolution_note,
            )

        # neuroglancer setting -- bind to this to make accessible outside of container
        neuroglancer.set_server_bind_address(
            PYTC_NEUROGLANCER_BIND_HOST, PYTC_NEUROGLANCER_PORT
        )
        viewer = neuroglancer.Viewer()
        # Neuroglancer expects the EM volume axes in z, y, x order.
        res = neuroglancer.CoordinateSpace(
            names=["z", "y", "x"], units=["nm", "nm", "nm"], scales=scales
        )
        try:
            im = load_volume(str(resolved_image_path), label="image")
        except Exception as e:
            raise HTTPException(
                status_code=400, detail=f"Failed to read image volume: {str(e)}"
            )
        try:
            gt = (
                load_volume(str(resolved_label_path), label="label")
                if resolved_label_path
                else None
            )
            if gt is not None:
                gt = _normalize_segmentation_volume_for_neuroglancer(gt)
        except Exception as e:
            raise HTTPException(
                status_code=400, detail=f"Failed to prepare label volume: {str(e)}"
            )

        def ngLayer(
            data,
            res,
            tt="image",
            oo=(0, 0, 0),
            *,
            image_shader: Optional[str] = None,
            segmentation_kwargs: Optional[dict[str, Any]] = None,
        ):
            try:
                return _build_neuroglancer_layer(
                    neuroglancer,
                    data,
                    res,
                    volume_type=tt,
                    voxel_offset=oo,
                    image_shader=image_shader or _resolve_raw_image_shader(),
                    segmentation_kwargs=segmentation_kwargs,
                )
            except Exception as exc:
                raise HTTPException(
                    status_code=400,
                    detail=f"Failed to prepare Neuroglancer {tt} layer: {exc}",
                ) from exc

        with viewer.txn() as s:
            s.layers.append(name="im", layer=ngLayer(im, res, tt="image"))
            if gt is not None:
                s.layers.append(
                    name="gt",
                    layer=ngLayer(
                        gt,
                        res,
                        tt="segmentation",
                    ),
                )

        internal_viewer_url = str(viewer)
        public_url = _build_neuroglancer_public_url(internal_viewer_url, req)
        viewer_token = _retain_neuroglancer_viewer(
            viewer,
            public_url=public_url,
            internal_viewer_url=internal_viewer_url,
            mode="visualization",
            workflow_id=workflow_id,
            image_path=str(resolved_image_path),
            label_path=str(resolved_label_path) if resolved_label_path else None,
        )
        append_app_event(
            component="server_api",
            event="neuroglancer_viewer_created",
            level="ERROR" if public_url.startswith("http://") else "INFO",
            message="Created Neuroglancer viewer URL.",
            internal_viewer_url=internal_viewer_url,
            public_url=public_url,
            public_url_scheme=urlsplit(public_url).scheme,
            bind_host=PYTC_NEUROGLANCER_BIND_HOST,
            bind_port=PYTC_NEUROGLANCER_PORT,
            configured_public_base=get_neuroglancer_public_base(),
            request_host=req.headers.get("host"),
            forwarded_proto=req.headers.get("x-forwarded-proto"),
            image_path=str(resolved_image_path),
            label_path=str(resolved_label_path) if resolved_label_path else None,
            image_shape=list(getattr(im, "shape", []) or []),
            label_shape=list(getattr(gt, "shape", []) or []) if gt is not None else None,
            scales=scales,
            workflow_id=workflow_id,
            viewer_token=viewer_token,
        )
        response_payload = {
            "url": public_url,
            "neuroglancer_url": public_url,
            "viewer_token": viewer_token,
            "image_path": str(resolved_image_path),
            "label_path": str(resolved_label_path) if resolved_label_path else None,
            "requested_image_path": str(original_image_path),
            "requested_label_path": str(original_label_path)
            if original_label_path
            else None,
            "image_resolution_note": image_resolution_note,
            "label_resolution_note": label_resolution_note,
            "scales": scales,
            "pair_discovery": pair_discovery,
            "pair_question": (
                "I found "
                f"{pair_discovery['pair_count']} clear image/segmentation pairs. "
                "I opened the first one. Are there other folders or pairs I should include?"
            )
            if pair_discovery["pair_count"] > 1
            else None,
        }
        if workflow_id:
            workflow = get_user_workflow_or_404(
                db, workflow_id=int(workflow_id), user_id=current_user.id
            )
            metadata = decode_json(workflow.metadata_json)
            metadata["active_volume_pair"] = {
                "image_path": str(resolved_image_path),
                "label_path": str(resolved_label_path) if resolved_label_path else None,
                "source": "neuroglancer",
            }
            metadata["visualization_scales"] = scales
            metadata["visualization_scales_source"] = "visualization"
            if pair_discovery["pair_count"]:
                metadata["volume_pair_discovery"] = {
                    "source": "neuroglancer",
                    "pair_count": pair_discovery["pair_count"],
                    "image_candidate_count": pair_discovery["image_candidate_count"],
                    "label_candidate_count": pair_discovery["label_candidate_count"],
                    "pairs": pair_discovery["pairs"][:12],
                    "unpaired_images": pair_discovery["unpaired_images"],
                    "unpaired_labels": pair_discovery["unpaired_labels"],
                    "requested_image_path": pair_discovery["requested_image_path"],
                    "requested_label_path": pair_discovery["requested_label_path"],
                }
            update_workflow_fields(
                db,
                workflow,
                {
                    "stage": "visualization",
                    "image_path": str(resolved_image_path),
                    "label_path": str(resolved_label_path) if resolved_label_path else None,
                    "neuroglancer_url": public_url,
                    "metadata": metadata,
                },
                commit=True,
            )
            append_event_for_workflow_if_present(
                db,
                workflow_id=workflow.id,
                actor="user",
                event_type="viewer.created",
                stage="visualization",
                summary="Created Neuroglancer viewer.",
                payload={
                    "image_path": str(resolved_image_path),
                    "label_path": str(resolved_label_path) if resolved_label_path else None,
                    "requested_image_path": str(original_image_path),
                    "requested_label_path": str(original_label_path)
                    if original_label_path
                    else None,
                    "image_resolution_note": image_resolution_note,
                    "label_resolution_note": label_resolution_note,
                    "pair_discovery": pair_discovery,
                    "pair_question": response_payload["pair_question"],
                    "scales": scales,
                    "neuroglancer_url": public_url,
                },
            )
        return response_payload
    finally:
        for path in cleanup_paths:
            try:
                path.unlink()
            except FileNotFoundError:
                pass
            except PermissionError:
                pass


@app.post("/neuroglancer/proofread")
async def neuroglancer_proofread(
    payload: NeuroglancerProofreadRequest,
    req: Request,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    import neuroglancer

    workflow_id = payload.workflow_id or payload.workflowId
    session_id = payload.session_id or payload.sessionId
    active_instance_id = payload.active_instance_id or payload.activeInstanceId
    image = process_path(payload.image) if payload.image else None
    label = process_path(payload.label) if payload.label else None
    scales = _coerce_neuroglancer_scales(payload.scales)
    session_context = None
    persistence_context = None

    if session_id:
        from server_api.ehtool.db_models import EHToolSession
        from server_api.ehtool.router import get_data_manager

        session_context = (
            db.query(EHToolSession)
            .filter(
                EHToolSession.id == int(session_id),
                EHToolSession.user_id == current_user.id,
            )
            .first()
        )
        if not session_context:
            raise HTTPException(status_code=404, detail="Proofreading session not found.")
        image = image or session_context.dataset_path
        label = label or session_context.mask_path
        workflow_id = workflow_id or session_context.workflow_id
        try:
            data_manager = get_data_manager(int(session_id), db)
            persistence_context = data_manager.get_persistence_status()
            if (
                persistence_context.get("artifact_exists")
                and persistence_context.get("artifact_path")
            ):
                label = persistence_context["artifact_path"]
        except Exception:
            logger.debug(
                "Unable to inspect proofreading persistence for Neuroglancer launch",
                exc_info=True,
            )

    if not image:
        raise HTTPException(
            status_code=400,
            detail="Image path is required to open Neuroglancer proofreading.",
        )

    original_image_path = pathlib.Path(image)
    original_label_path = pathlib.Path(label) if label else None
    if not original_image_path.exists():
        _raise_missing_volume_error(original_image_path, "image")
    if original_label_path is not None and not original_label_path.exists():
        _raise_missing_volume_error(original_label_path, "label")

    try:
        resolved_image_path, image_resolution_note = _resolve_neuroglancer_image_path(
            original_image_path,
            original_label_path,
        )
        resolved_label_path, label_resolution_note = _resolve_neuroglancer_label_path(
            original_label_path,
            resolved_image_path,
        )
    except ValueError as exc:
        append_app_event(
            component="server_api",
            event="neuroglancer_proofread_resolution_failed",
            level="ERROR",
            message=str(exc),
            image_path=str(original_image_path),
            label_path=str(original_label_path) if original_label_path else None,
            session_id=session_id,
            workflow_id=workflow_id,
        )
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    try:
        im = load_volume(str(resolved_image_path), label="image")
    except Exception as exc:
        raise HTTPException(
            status_code=400, detail=f"Failed to read image volume: {str(exc)}"
        ) from exc

    gt = None
    if resolved_label_path:
        try:
            gt = load_volume(str(resolved_label_path), label="label")
            gt = _normalize_segmentation_volume_for_neuroglancer(gt)
        except Exception as exc:
            raise HTTPException(
                status_code=400,
                detail=f"Failed to prepare label volume for proofreading: {str(exc)}",
            ) from exc

    neuroglancer.set_server_bind_address(
        PYTC_NEUROGLANCER_BIND_HOST, PYTC_NEUROGLANCER_PORT
    )
    viewer = neuroglancer.Viewer()
    dimensions = neuroglancer.CoordinateSpace(
        names=["z", "y", "x"], units=["nm", "nm", "nm"], scales=scales
    )

    def make_local_volume(data, volume_type: str, voxel_offset=(0, 0, 0)):
        try:
            return _build_neuroglancer_local_volume_source(
                neuroglancer,
                data,
                dimensions,
                volume_type=volume_type,
                voxel_offset=voxel_offset,
            )
        except Exception as exc:
            raise HTTPException(
                status_code=400,
                detail=f"Failed to prepare Neuroglancer {volume_type} layer: {exc}",
            ) from exc

    image_layer = _build_neuroglancer_layer(
        neuroglancer,
        im,
        dimensions,
        volume_type="image",
        voxel_offset=[0, 0, 0],
    )
    segmentation_source = make_local_volume(gt, "segmentation") if gt is not None else None
    initial_voxel = _coerce_initial_voxel(
        payload.initial_voxel or payload.initialVoxel,
        tuple(getattr(im, "shape", ()) or ()),
    )

    def append_point(layer_name: str, coordinates, description: str):
        if coordinates is None:
            return
        point = [float(value) for value in coordinates]
        with viewer.txn() as state:
            if state.layers.index(layer_name) == -1:
                return
            layer = state.layers[layer_name]
            annotations = list(layer.annotations)
            annotations.append(
                dict(
                    type="point",
                    id=str(uuid.uuid4()),
                    point=point,
                    description=description,
                )
            )
            layer.annotations = annotations

    def handle_marker_action(action_type: str, layer_name: str, description: str):
        def _handler(action_state):
            coordinates = getattr(action_state, "mouse_voxel_coordinates", None)
            if coordinates is None:
                return
            selected_segment = _selected_segment_from_action_state(
                action_state,
                ["selected-instance", "segmentation"],
            )
            point = [float(value) for value in coordinates]
            marker_description = description
            if selected_segment is not None:
                marker_description = f"{description}; segment {selected_segment}"
            append_point(layer_name, point, marker_description)
            _record_neuroglancer_proofread_action(
                workflow_id=workflow_id,
                action_type=action_type,
                payload={
                    "coordinates_zyx": point,
                    "selected_segment": selected_segment,
                    "session_id": session_id,
                    "active_instance_id": active_instance_id,
                    "image_path": str(resolved_image_path),
                    "label_path": str(resolved_label_path)
                    if resolved_label_path
                    else None,
                },
            )
            with viewer.config_state.txn() as config:
                config.status_messages["pytc-last-action"] = marker_description

        return _handler

    def handle_save_review(_action_state):
        _record_neuroglancer_proofread_action(
            workflow_id=workflow_id,
            action_type="save_review_checkpoint",
            payload={
                "session_id": session_id,
                "active_instance_id": active_instance_id,
                "image_path": str(resolved_image_path),
                "label_path": str(resolved_label_path) if resolved_label_path else None,
            },
        )
        with viewer.config_state.txn() as config:
            config.status_messages["pytc-last-action"] = (
                "Saved Neuroglancer proofreading checkpoint to the workflow log."
            )

    key_bindings = [
        ("control+mousedown0", "pytc-merge-source", "merge source"),
        ("control+shift+mousedown0", "pytc-merge-target", "merge target"),
        ("shift+mousedown0", "pytc-split-seed", "split seed"),
        ("alt+mousedown0", "pytc-needs-fix", "needs-fix marker"),
        ("control+keys", "pytc-save-review", "save review checkpoint"),
    ]
    viewer.actions.add(
        "pytc-merge-source",
        handle_marker_action("merge_source", "merge-points", "merge source"),
    )
    viewer.actions.add(
        "pytc-merge-target",
        handle_marker_action("merge_target", "merge-points", "merge target"),
    )
    viewer.actions.add(
        "pytc-split-seed",
        handle_marker_action("split_seed", "split-seeds", "split seed"),
    )
    viewer.actions.add(
        "pytc-needs-fix",
        handle_marker_action("needs_fix", "needs-fix", "needs-fix marker"),
    )
    viewer.actions.add("pytc-save-review", handle_save_review)

    layer_names = ["image"]
    with viewer.txn() as state:
        state.layers.append(name="image", layer=image_layer)
        if segmentation_source is not None:
            state.layers.append(
                name="segmentation",
                layer=neuroglancer.SegmentationLayer(
                    source=segmentation_source,
                    object_alpha=0.34,
                    selected_alpha=0.7,
                    not_selected_alpha=0.18,
                ),
            )
            layer_names.append("segmentation")
            if active_instance_id:
                state.layers.append(
                    name="selected-instance",
                    layer=neuroglancer.SegmentationLayer(
                        source=segmentation_source,
                        segments={int(active_instance_id)},
                        object_alpha=0.86,
                        segment_colors={int(active_instance_id): "#f72585"},
                    ),
                )
                layer_names.append("selected-instance")
        state.layers.append(
            name="merge-points",
            layer=neuroglancer.LocalAnnotationLayer(
                dimensions=dimensions,
                annotation_color="#22d3ee",
                annotations=[],
            ),
        )
        state.layers.append(
            name="split-seeds",
            layer=neuroglancer.LocalAnnotationLayer(
                dimensions=dimensions,
                annotation_color="#f59e0b",
                annotations=[],
            ),
        )
        state.layers.append(
            name="needs-fix",
            layer=neuroglancer.LocalAnnotationLayer(
                dimensions=dimensions,
                annotation_color="#ef4444",
                annotations=[],
            ),
        )
        layer_names.extend(["merge-points", "split-seeds", "needs-fix"])
        if initial_voxel:
            state.voxel_coordinates = initial_voxel
        state.show_slices = True
        state.layout = neuroglancer.row_layout(
            [
                neuroglancer.LayerGroupViewer(layout="xy", layers=layer_names),
                neuroglancer.LayerGroupViewer(layout="3d", layers=layer_names),
            ]
        )

    with viewer.config_state.txn() as config:
        config.status_messages["pytc-proofread"] = (
            "PyTC Neuroglancer proofread: ctrl-click merge source, "
            "ctrl-shift-click merge target, shift-click split seed, "
            "alt-click needs-fix, ctrl-s logs checkpoint."
        )
        for binding, command, _label in key_bindings:
            config.input_event_bindings.viewer[binding] = command
            config.input_event_bindings.data_view[binding] = command
            config.input_event_bindings.slice_view[binding] = command
            config.input_event_bindings.perspective_view[binding] = command

    internal_viewer_url = str(viewer)
    public_url = _build_neuroglancer_public_url(internal_viewer_url, req)
    viewer_token = _retain_neuroglancer_viewer(
        viewer,
        public_url=public_url,
        internal_viewer_url=internal_viewer_url,
        mode="proofreading",
        workflow_id=workflow_id,
        image_path=str(resolved_image_path),
        label_path=str(resolved_label_path) if resolved_label_path else None,
    )
    response_payload = {
        "url": public_url,
        "neuroglancer_url": public_url,
        "viewer_token": viewer_token,
        "mode": "proofreading",
        "image_path": str(resolved_image_path),
        "label_path": str(resolved_label_path) if resolved_label_path else None,
        "requested_image_path": str(original_image_path),
        "requested_label_path": str(original_label_path) if original_label_path else None,
        "image_resolution_note": image_resolution_note,
        "label_resolution_note": label_resolution_note,
        "scales": scales,
        "workflow_id": workflow_id,
        "session_id": session_id,
        "active_instance_id": active_instance_id,
        "persistence": persistence_context,
        "controls": [
            {"gesture": binding, "action": label}
            for binding, _command, label in key_bindings
        ],
    }

    if workflow_id:
        workflow = get_user_workflow_or_404(
            db, workflow_id=int(workflow_id), user_id=current_user.id
        )
        metadata = decode_json(workflow.metadata_json)
        metadata["neuroglancer_proofreading"] = {
            "url": public_url,
            "image_path": str(resolved_image_path),
            "label_path": str(resolved_label_path) if resolved_label_path else None,
            "session_id": session_id,
            "active_instance_id": active_instance_id,
            "controls": response_payload["controls"],
            "launched_at": datetime.now(timezone.utc).isoformat(),
        }
        update_workflow_fields(
            db,
            workflow,
            {
                "stage": "proofreading",
                "image_path": str(resolved_image_path),
                "mask_path": str(resolved_label_path) if resolved_label_path else None,
                "neuroglancer_url": public_url,
                "metadata": metadata,
            },
            commit=True,
        )
        append_event_for_workflow_if_present(
            db,
            workflow_id=workflow.id,
            actor="user",
            event_type="proofreading.neuroglancer_viewer_created",
            stage="proofreading",
            summary="Created Neuroglancer proofreading viewer.",
            payload=response_payload,
        )

    append_app_event(
        component="server_api",
        event="neuroglancer_proofread_created",
        message="Created Neuroglancer proofreading viewer.",
        workflow_id=workflow_id,
        session_id=session_id,
        active_instance_id=active_instance_id,
        image_path=str(resolved_image_path),
        label_path=str(resolved_label_path) if resolved_label_path else None,
        neuroglancer_url=public_url,
        viewer_token=viewer_token,
    )
    return response_payload


@app.post("/start_model_training")
async def start_model_training(
    req: Request,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    body = await req.json()
    append_app_event(
        component="server_api",
        event="training_request_received",
        level="INFO",
        message="Training request received by API",
        source="api_endpoint",
        payload_keys=sorted(body.keys()),
        config_origin_path=body.get("configOriginPath"),
        output_path=body.get("outputPath"),
        log_path=body.get("logPath"),
        training_config_length=len(body.get("trainingConfig") or ""),
        workflow_id=body.get("workflow_id") or body.get("workflowId"),
        user_id=current_user.id,
    )
    workflow_id = body.get("workflow_id") or body.get("workflowId")
    if workflow_id:
        workflow = get_user_workflow_or_404(
            db, workflow_id=int(workflow_id), user_id=current_user.id
        )
        body = _runtime_body_with_workflow_fallbacks(
            body,
            workflow,
            mode="training",
        )
        update_workflow_fields(
            db,
            workflow,
            {
                "stage": "retraining_staged",
                "training_output_path": body.get("outputPath"),
            },
            commit=True,
        )
        append_event_for_workflow_if_present(
            db,
            workflow_id=workflow.id,
            actor="user",
            event_type="training.started",
            stage=workflow.stage,
            summary="Started model training from the workflow.",
            payload={
                "outputPath": body.get("outputPath"),
                "logPath": body.get("logPath"),
                "configOriginPath": body.get("configOriginPath"),
                "inputImagePath": body.get("inputImagePath"),
                "inputLabelPath": body.get("inputLabelPath"),
            },
        )
    worker_data = _proxy_to_worker(
        "post",
        "/start_model_training",
        json_body=body,
        timeout=30,
    )
    return {
        "message": "Model training started successfully",
        "data": worker_data,
    }


@app.post("/api/workflows/{workflow_id}/commands/{command_id}/run")
async def run_workflow_command(
    workflow_id: int,
    command_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    workflow = get_user_workflow_or_404(
        db, workflow_id=int(workflow_id), user_id=current_user.id
    )
    command = (
        db.query(WorkflowCommand)
        .filter(
            WorkflowCommand.id == command_id,
            WorkflowCommand.workflow_id == workflow.id,
        )
        .first()
    )
    if not command:
        raise HTTPException(status_code=404, detail="Workflow command not found.")
    if command.command_type != "start_training":
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported workflow command type: {command.command_type}",
        )

    try:
        body = _build_training_body_from_command(command, workflow)
        body = _runtime_body_with_workflow_fallbacks(body, workflow, mode="training")
        command = mark_workflow_command_running(
            db,
            command,
            lease_owner="server_api.training_runner",
            commit=True,
        )
        update_workflow_fields(
            db,
            workflow,
            {
                "stage": "retraining_staged",
                "training_output_path": body.get("outputPath"),
                "config_path": body.get("configOriginPath"),
            },
            commit=True,
        )
        started_event = append_event_for_workflow_if_present(
            db,
            workflow_id=workflow.id,
            actor="system",
            event_type="training.started",
            stage=workflow.stage,
            summary="Started model training from a durable workflow command.",
            payload={
                "run_id": body.get("run_id"),
                "command_id": command.id,
                "outputPath": body.get("outputPath"),
                "logPath": body.get("logPath"),
                "configOriginPath": body.get("configOriginPath"),
                "inputImagePath": body.get("inputImagePath"),
                "inputLabelPath": body.get("inputLabelPath"),
                "source": "workflow_command_runner",
            },
            idempotency_key=f"workflow-command:{command.id}:training.started",
        )
        worker_data = _proxy_to_worker(
            "post",
            "/start_model_training",
            json_body=body,
            timeout=30,
        )
        command = submit_workflow_command(
            db,
            command,
            result_payload={
                "worker": worker_data,
                "run_id": body.get("run_id"),
                "started_event_id": started_event.id if started_event else None,
                "submitted": True,
            },
            commit=True,
        )
        return {
            "workflow_id": workflow.id,
            "command": command_to_dict(command),
            "worker": worker_data,
            "run_id": body.get("run_id"),
            "started_event_id": started_event.id if started_event else None,
        }
    except HTTPException as exc:
        error_payload = {
            "error": "HTTPException",
            "status_code": exc.status_code,
            "detail": exc.detail,
        }
        fail_workflow_command(
            db,
            command,
            error_payload=error_payload,
            retryable=exc.status_code in {503, 504},
            commit=True,
        )
        append_event_for_workflow_if_present(
            db,
            workflow_id=workflow.id,
            actor="system",
            event_type="training.failed",
            stage=workflow.stage,
            summary="Failed to start model training from a durable workflow command.",
            payload={
                "command_id": command.id,
                "source": "workflow_command_runner",
                **error_payload,
            },
            idempotency_key=f"workflow-command:{command.id}:training.failed",
        )
        raise
    except Exception as exc:
        error_payload = {
            "error": type(exc).__name__,
            "detail": str(exc),
        }
        fail_workflow_command(
            db,
            command,
            error_payload=error_payload,
            retryable=False,
            commit=True,
        )
        append_event_for_workflow_if_present(
            db,
            workflow_id=workflow.id,
            actor="system",
            event_type="training.failed",
            stage=workflow.stage,
            summary="Failed to start model training from a durable workflow command.",
            payload={
                "command_id": command.id,
                "source": "workflow_command_runner",
                **error_payload,
            },
            idempotency_key=f"workflow-command:{command.id}:training.failed",
        )
        raise HTTPException(status_code=500, detail=error_payload) from exc


@app.post("/stop_model_training")
async def stop_model_training():
    worker_data = _proxy_to_worker("post", "/stop_model_training", timeout=30)
    return {
        "message": "Model training stopped successfully",
        "data": worker_data,
    }


@app.get("/training_status")
async def get_training_status():
    """Proxy training status check to PyTC server"""
    return _proxy_to_worker("get", "/training_status", timeout=5)


@app.get("/training_logs")
async def get_training_logs():
    return _proxy_to_worker("get", "/training_logs", timeout=5)


@app.post("/start_model_inference")
async def start_model_inference(
    req: Request,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    body = await req.json()
    append_app_event(
        component="server_api",
        event="inference_request_received",
        level="INFO",
        message="Inference request received by API",
        source="api_endpoint",
        payload_keys=sorted(body.keys()),
        config_origin_path=body.get("configOriginPath"),
        output_path=body.get("outputPath"),
        checkpoint_path=(body.get("arguments") or {}).get("checkpoint")
        or body.get("checkpointPath"),
        inference_config_length=len(body.get("inferenceConfig") or ""),
        workflow_id=body.get("workflow_id") or body.get("workflowId"),
        user_id=current_user.id,
    )
    workflow_id = body.get("workflow_id") or body.get("workflowId")
    if workflow_id:
        workflow = get_user_workflow_or_404(
            db, workflow_id=int(workflow_id), user_id=current_user.id
        )
        body = _runtime_body_with_workflow_fallbacks(
            body,
            workflow,
            mode="inference",
        )
        update_workflow_fields(
            db,
            workflow,
            {
                "stage": "inference",
                "inference_output_path": body.get("outputPath"),
                "checkpoint_path": (body.get("arguments") or {}).get("checkpoint")
                or body.get("checkpointPath"),
            },
            commit=True,
        )
        append_event_for_workflow_if_present(
            db,
            workflow_id=workflow.id,
            actor="user",
            event_type="inference.started",
            stage="inference",
            summary="Started model inference from the workflow.",
            payload={
                "outputPath": body.get("outputPath"),
                "checkpointPath": (body.get("arguments") or {}).get("checkpoint")
                or body.get("checkpointPath"),
                "configOriginPath": body.get("configOriginPath"),
            },
        )
    worker_data = _proxy_to_worker(
        "post",
        "/start_model_inference",
        json_body=body,
        timeout=30,
    )
    return {
        "message": "Model inference started successfully",
        "data": worker_data,
    }


@app.post("/stop_model_inference")
async def stop_model_inference():
    worker_data = _proxy_to_worker("post", "/stop_model_inference", timeout=30)
    return {
        "message": "Model inference stopped successfully",
        "data": worker_data,
    }


@app.get("/inference_status")
async def get_inference_status():
    return _proxy_to_worker("get", "/inference_status", timeout=5)


@app.get("/inference_logs")
async def get_inference_logs():
    return _proxy_to_worker("get", "/inference_logs", timeout=5)


@app.post("/api/workflows/{workflow_id}/sync-inference-runtime")
async def sync_workflow_inference_runtime(
    workflow_id: int,
    body: Optional[WorkflowInferenceRuntimeSyncRequest] = None,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    workflow = get_user_workflow_or_404(
        db, workflow_id=int(workflow_id), user_id=current_user.id
    )
    runtime = _proxy_to_worker("get", "/inference_logs", timeout=5) or {}
    metadata = runtime.get("metadata") if isinstance(runtime, dict) else {}
    metadata = metadata if isinstance(metadata, dict) else {}
    phase = runtime.get("phase") if isinstance(runtime, dict) else None
    checkpoint_path = _metadata_path(
        metadata,
        "checkpointPath",
        "latestCheckpointPath",
        "checkpoint",
    )
    output_directory = _metadata_path(metadata, "outputPath", "output_path")
    prediction_path = _metadata_path(
        metadata,
        "predictionPath",
        "latestPredictionPath",
        "outputPredictionPath",
    ) or _discover_prediction_output(output_directory)

    if phase not in {"finished", "failed"}:
        return {
            "synced": False,
            "phase": phase or "unknown",
            "reason": "runtime_not_terminal",
            "metadata": metadata,
        }

    runtime_payload = {
        "source": "runtime_sync",
        "runtimePhase": phase,
        "runtimePid": runtime.get("pid") if isinstance(runtime, dict) else None,
        "runtimeExitCode": (
            runtime.get("exitCode") if isinstance(runtime, dict) else None
        ),
        "runtimeStartedAt": (
            runtime.get("startedAt") if isinstance(runtime, dict) else None
        ),
        "runtimeEndedAt": runtime.get("endedAt") if isinstance(runtime, dict) else None,
        "runtimeLineCount": (
            runtime.get("lineCount") if isinstance(runtime, dict) else None
        ),
        "outputDirectory": output_directory,
        "checkpointPath": checkpoint_path,
        "configPath": runtime.get("configPath") if isinstance(runtime, dict) else None,
        "configOriginPath": (
            runtime.get("configOriginPath") if isinstance(runtime, dict) else None
        )
        or metadata.get("configOriginPath"),
        "workflowId": metadata.get("workflowId") or workflow_id,
        "predictionName": (
            pathlib.Path(prediction_path).name if prediction_path else None
        ),
    }

    if phase == "failed":
        ended_at = runtime_payload.get("runtimeEndedAt")
        existing = _find_synced_inference_event(
            db,
            workflow_id=workflow.id,
            event_type="inference.failed",
            ended_at=ended_at,
        )
        if existing is None:
            append_event_for_workflow_if_present(
                db,
                workflow_id=workflow.id,
                actor="system",
                event_type="inference.failed",
                stage="inference",
                summary="Synchronized failed PyTC inference runtime.",
                payload={
                    **runtime_payload,
                    "lastError": (
                        runtime.get("lastError") if isinstance(runtime, dict) else None
                    ),
                },
            )
        return {
            "synced": True,
            "phase": phase,
            "event_type": "inference.failed",
            "deduplicated": existing is not None,
        }

    if not prediction_path:
        return {
            "synced": False,
            "phase": phase,
            "reason": "prediction_artifact_not_found",
            "metadata": metadata,
        }

    requested_stage = body.stage if body else None
    target_stage = requested_stage or (
        "evaluation"
        if workflow.stage in {"retraining_staged", "evaluation"}
        else "inference"
    )
    update_payload = {
        "stage": target_stage,
        "inference_output_path": prediction_path,
    }
    if checkpoint_path:
        update_payload["checkpoint_path"] = checkpoint_path
    update_workflow_fields(db, workflow, update_payload, commit=True)

    existing = _find_synced_inference_event(
        db,
        workflow_id=workflow.id,
        event_type="inference.completed",
        output_path=prediction_path,
        ended_at=runtime_payload.get("runtimeEndedAt"),
    )
    event = existing
    if event is None:
        event = append_event_for_workflow_if_present(
            db,
            workflow_id=workflow.id,
            actor="system",
            event_type="inference.completed",
            stage=target_stage,
            summary="Synchronized completed PyTC inference output.",
            payload={
                **runtime_payload,
                "outputPath": prediction_path,
                "latestPredictionPath": prediction_path,
            },
        )

    return {
        "synced": True,
        "phase": phase,
        "event_type": "inference.completed",
        "event_id": event.id if event else None,
        "deduplicated": existing is not None,
        "outputPath": prediction_path,
        "checkpointPath": checkpoint_path,
        "stage": target_stage,
    }


@app.get("/start_tensorboard")
async def start_tensorboard(logPath: Optional[str] = None):
    return _proxy_to_worker(
        "get",
        "/start_tensorboard",
        params={"logPath": logPath} if logPath else None,
        timeout=30,
    )


@app.get("/get_tensorboard_url")
async def get_tensorboard_url():
    return _proxy_to_worker("get", "/get_tensorboard_url", timeout=5)


@app.get("/get_tensorboard_status")
async def get_tensorboard_status():
    return _proxy_to_worker("get", "/get_tensorboard_status", timeout=5)


# TODO: Improve on this: basic idea: labels are binary -- black or white?
# Check the unique values: Assume that the label should have 0 or 255
# This is temporarily ditched in favor of allowing users to specify whether or not a file is a label or image.


@app.post("/check_files")
async def check_files(req: Request):
    import numpy as np
    import os

    try:
        im = await req.json()
        print(f"Received check_files payload: {im}")
        print(im.get("folderPath"), im.get("name"))

        # Use os.path.join for safe path construction
        if "filePath" in im and im["filePath"]:
            image_path = im["filePath"]
        else:
            image_path = os.path.join(im["folderPath"], im["name"])

        print(f"Checking file at: {image_path}")

        try:
            # Use readVol to support all project-standard formats (TIFF, H5, etc.)
            image_array = readVol(image_path, image_type="im")
        except Exception as e:
            print(f"Failed to read file: {e}")
            return {"error": f"Failed to open image: {str(e)}"}

        unique_values = np.unique(image_array)
        num_unique = len(unique_values)
        is_label = _is_probable_label_volume(image_array)

        if is_label:
            print(
                f"The image {im['name']} is likely a label (unique values: {num_unique})"
            )
            label = True
        else:
            print(
                f"The image {im['name']} is likely not a label (unique values: {num_unique})"
            )
            label = False

        return {"label": label}
    except Exception as e:
        return {"error": str(e)}


# ── Chat history persistence endpoints ─────────────────────────────────────────


@app.get("/chat/conversations", response_model=List[models.ConversationResponse])
def list_conversations(
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return all conversations for the current user, newest first."""
    return (
        db.query(models.Conversation)
        .filter(models.Conversation.user_id == user.id)
        .order_by(models.Conversation.updated_at.desc())
        .all()
    )


@app.post("/chat/conversations", response_model=models.ConversationDetailResponse)
def create_conversation(
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a new empty conversation."""
    convo = models.Conversation(user_id=user.id, title="New Chat")
    db.add(convo)
    db.commit()
    db.refresh(convo)
    return convo


@app.get(
    "/chat/conversations/{convo_id}",
    response_model=models.ConversationDetailResponse,
)
def get_conversation(
    convo_id: int,
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return a conversation and all its messages."""
    convo = (
        db.query(models.Conversation)
        .filter(
            models.Conversation.id == convo_id,
            models.Conversation.user_id == user.id,
        )
        .first()
    )
    if not convo:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return convo


@app.delete("/chat/conversations/{convo_id}")
def delete_conversation(
    convo_id: int,
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete a conversation and all its messages."""
    convo = (
        db.query(models.Conversation)
        .filter(
            models.Conversation.id == convo_id,
            models.Conversation.user_id == user.id,
        )
        .first()
    )
    if not convo:
        raise HTTPException(status_code=404, detail="Conversation not found")
    db.delete(convo)
    db.commit()
    # Clear in-memory history if we just deleted the active conversation
    global _active_convo_id, _chat_history
    if _active_convo_id == convo_id:
        _active_convo_id = None
        _chat_history.clear()
    return {"message": "Conversation deleted"}


@app.patch(
    "/chat/conversations/{convo_id}",
    response_model=models.ConversationResponse,
)
def update_conversation(
    convo_id: int,
    req_body: dict,
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update a conversation's title."""
    convo = (
        db.query(models.Conversation)
        .filter(
            models.Conversation.id == convo_id,
            models.Conversation.user_id == user.id,
        )
        .first()
    )
    if not convo:
        raise HTTPException(status_code=404, detail="Conversation not found")
    if "title" in req_body:
        title = str(req_body["title"] or "").strip()
        if not title:
            raise HTTPException(status_code=400, detail="Title must be non-empty")
        convo.title = title[:120]  # cap at 120 chars
        convo.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(convo)
    return convo


def _load_history_for_convo(convo_id: int, db: Session):
    """Rebuild the in-memory _chat_history from the DB for a given conversation."""
    global _active_convo_id, _chat_history
    if _active_convo_id == convo_id:
        return  # already loaded
    msgs = (
        db.query(models.ChatMessage)
        .filter(models.ChatMessage.conversation_id == convo_id)
        .order_by(models.ChatMessage.created_at)
        .all()
    )
    _chat_history = [{"role": m.role, "content": m.content} for m in msgs]
    _active_convo_id = convo_id


# Chatbot endpoints
def _direct_general_chat_response(query: str) -> Optional[str]:
    lower = query.strip().lower()
    compact = re.sub(r"[^a-z0-9]+", "", lower)
    if not compact:
        return None

    vowel_count = len(re.findall(r"[aeiou]", compact))
    looks_like_gibberish_token = (
        len(compact) >= 8
        and " " not in lower
        and vowel_count <= 2
        and not lower.startswith("/")
    )
    if looks_like_gibberish_token:
        return (
            "I did not understand that.\n"
            "Try a workflow job like: run inference, proofread, train on saved edits, compare results, or status."
        )

    quick_run_phrases = [
        "how do you run so quickly",
        "how did you run so quickly",
        "why did you run so quickly",
        "did you actually run",
        "are you actually running",
    ]
    if any(phrase in lower for phrase in quick_run_phrases):
        return (
            "I did not run training or inference there.\n"
            "I answered from existing workflow/docs context, which is fast.\n"
            "Long jobs still require your approval and should show progress."
        )

    parameter_phrases = [
        "do i need to set parameters",
        "do i need to tune",
        "choose parameters",
        "pick parameters",
        "infer parameters",
        "stride",
        "blending",
        "chunk",
    ]
    if any(phrase in lower for phrase in parameter_phrases) and any(
        term in lower for term in ["agent", "you", "biologist", "training", "inference"]
    ):
        return (
            "You should not have to tune low-level parameters by default.\n"
            "Do this: give me the image/mask goal and approve the run; I should choose a safe preset and defaults.\n"
            "Use advanced settings only when you explicitly want to override me."
        )

    return None


def _persist_chat_exchange(
    db: Session,
    *,
    conversation: models.Conversation,
    query: str,
    response: str,
    source: Optional[str] = None,
) -> None:
    db.add(
        models.ChatMessage(conversation_id=conversation.id, role="user", content=query)
    )
    db.add(
        models.ChatMessage(
            conversation_id=conversation.id,
            role="assistant",
            content=response,
            source=source,
        )
    )
    if conversation.title == "New Chat":
        conversation.title = query[:120].strip() or "New Chat"
    conversation.updated_at = datetime.now(timezone.utc)


def _get_or_create_chat_conversation(
    db: Session, *, user_id: int, conversation_id: Optional[int]
) -> models.Conversation:
    if not conversation_id:
        convo = models.Conversation(user_id=user_id, title="New Chat")
        db.add(convo)
        db.commit()
        db.refresh(convo)
        return convo

    convo = (
        db.query(models.Conversation)
        .filter(
            models.Conversation.id == conversation_id,
            models.Conversation.user_id == user_id,
        )
        .first()
    )
    if not convo:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return convo


@app.post("/chat/query")
async def chat_query(
    req: Request,
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    global _chatbot_error
    request_id = request_id_from_request(req).replace("-", "")[:8]
    request_start = time.perf_counter()
    print(f"[CHATBOT][{request_id}] Incoming /chat/query request from user={user.id}")
    body = await req.json()
    query = body.get("query")
    convo_id = body.get("conversationId")
    if not isinstance(query, str) or not query.strip():
        raise HTTPException(status_code=400, detail="Query must be a non-empty string.")
    print(
        f"[CHATBOT][{request_id}] Parsed request: convo_id={convo_id}, "
        f"query_len={len(query.strip())}"
    )

    convo = _get_or_create_chat_conversation(
        db, user_id=user.id, conversation_id=convo_id
    )
    convo_id = convo.id

    direct_response = _direct_general_chat_response(query)
    if direct_response:
        _persist_chat_exchange(
            db,
            conversation=convo,
            query=query,
            response=direct_response,
            source="direct_guard",
        )
        db.commit()
        log_request_summary(
            request_id=request_id,
            endpoint="/chat/query",
            start_time=request_start,
            status="ok",
        )
        return {
            "response": direct_response,
            "conversationId": convo_id,
            "source": "direct_guard",
        }

    if not _ensure_chatbot():
        print(f"[CHATBOT][{request_id}] Main chain unavailable before request")
        response = _llm_unavailable_chat_response()
        _persist_chat_exchange(
            db,
            conversation=convo,
            query=query,
            response=response,
            source="llm_unavailable",
        )
        db.commit()
        log_request_summary(
            request_id=request_id,
            endpoint="/chat/query",
            start_time=request_start,
            status="degraded",
            error_type="llm_unavailable",
        )
        return {
            "response": response,
            "conversationId": convo_id,
            "source": "llm_unavailable",
        }

    # Rebuild in-memory history from DB when switching conversations
    _load_history_for_convo(convo_id, db)
    print(
        f"[CHATBOT][{request_id}] Loaded history messages={len(_chat_history)} "
        f"for convo_id={convo_id}"
    )

    if _reset_search is not None:
        _reset_search()
        print(f"[CHATBOT][{request_id}] Reset documentation search call counter")
    all_messages = _chat_history + [{"role": "user", "content": query}]
    print(
        f"[CHATBOT][{request_id}] Invoking main chain with "
        f"{len(all_messages)} message(s)"
    )
    try:
        result = _invoke_with_progress(
            lambda: chain.invoke({"messages": all_messages}),
            label="main chain invoke",
            request_id=request_id,
        )
    except Exception as exc:
        _chatbot_error = exc
        print("[CHATBOT] LLM request failed: " f"{exc.__class__.__name__}: {exc!r}")
        traceback.print_exc()
        response = _llm_unavailable_chat_response()
        _persist_chat_exchange(
            db,
            conversation=convo,
            query=query,
            response=response,
            source="llm_unavailable",
        )
        db.commit()
        log_request_summary(
            request_id=request_id,
            endpoint="/chat/query",
            start_time=request_start,
            status="degraded",
            error_type=exc.__class__.__name__,
        )
        return {
            "response": response,
            "conversationId": convo_id,
            "source": "llm_unavailable",
        }
    messages = result.get("messages", [])
    response = messages[-1].content if messages else "No response generated"
    response = _compact_agent_response(response)
    response = _sanitize_agent_response(response)
    print(
        f"[CHATBOT][{request_id}] Chain returned messages={len(messages)}, "
        f"response_len={len(response) if isinstance(response, str) else 0}"
    )

    _persist_chat_exchange(
        db,
        conversation=convo,
        query=query,
        response=response,
        source="llm",
    )
    db.commit()

    # Update in-memory history
    _chat_history.append({"role": "user", "content": query})
    _chat_history.append({"role": "assistant", "content": response})
    total_elapsed = time.perf_counter() - request_start
    print(
        f"[CHATBOT][{request_id}] /chat/query completed in {total_elapsed:.2f}s "
        f"(convo_id={convo_id})"
    )
    log_request_summary(
        request_id=request_id,
        endpoint="/chat/query",
        start_time=request_start,
        status="ok",
    )

    return {"response": response, "conversationId": convo_id, "source": "llm"}


@app.post("/chat/clear")
async def clear_chat(
    user: models.User = Depends(get_current_user),
):
    """Reset the in-memory LangChain context (does NOT delete DB messages)."""
    global _active_convo_id, _chat_history
    if _reset_search is not None:
        _reset_search()
    _chat_history.clear()
    _active_convo_id = None
    return {"message": "Chat session reset"}


@app.get("/chat/status")
async def chat_status():
    configured = _ensure_chatbot()
    detail = None
    if not configured and "_chatbot_error" in globals():
        detail = str(_chatbot_error)
    return {"configured": configured, "error": detail}


# ---------------------------------------------------------------------------
# Helper chat endpoints (inline "?" popovers — RAG only, no training/inference)
# ---------------------------------------------------------------------------

_INLINE_HELP_DOCS_CACHE: Optional[dict[str, str]] = None


def _inline_helper_mode() -> str:
    return os.getenv("PYTC_INLINE_HELP_MODE", "docs").strip().lower()


def _load_inline_help_docs() -> dict[str, str]:
    global _INLINE_HELP_DOCS_CACHE
    if _INLINE_HELP_DOCS_CACHE is not None:
        return _INLINE_HELP_DOCS_CACHE

    docs_dir = BASE_DIR / "server_api" / "chatbot" / "file_summaries"
    docs: dict[str, str] = {}
    if docs_dir.is_dir():
        for path in docs_dir.rglob("*.md"):
            docs[path.name] = path.read_text(encoding="utf-8", errors="ignore")
    _INLINE_HELP_DOCS_CACHE = docs
    return docs


def _helper_tokens(*values: Optional[str]) -> set[str]:
    text = " ".join(value or "" for value in values).lower()
    return {
        token
        for token in re.findall(r"[a-z0-9_]+", text)
        if len(token) >= 3 and token not in {"the", "and", "for", "this", "that"}
    }


def _extract_helper_snippet(
    content: str, tokens: set[str], *, max_lines: int = 3
) -> str:
    lines = [line.strip() for line in content.splitlines() if line.strip()]
    matching = [
        line
        for line in lines
        if any(token in line.lower() for token in tokens)
        and not line.lower().startswith("image:")
    ]
    selected = matching[:max_lines] or lines[:max_lines]
    return "\n".join(selected)


def _history_text(history: Optional[list]) -> str:
    if not isinstance(history, list):
        return ""
    parts = []
    for item in history[-8:]:
        if not isinstance(item, dict):
            continue
        content = str(item.get("content") or "").strip()
        if content:
            parts.append(content)
    return " ".join(parts)


def _looks_like_initial_helper_prompt(query: str) -> bool:
    lower = query.lower()
    return "give concise help for this setting" in lower or "label:" in lower


def _is_casual_helper_message(query: str) -> bool:
    compact = re.sub(r"[^a-z0-9]+", "", query.lower())
    return compact in {"hi", "hello", "hey", "yo", "sup", "thanks", "thankyou"}


def _direct_inline_help(
    query: str, field_context: str, history: Optional[list] = None
) -> Optional[str]:
    normalized_query = query.lower()
    normalized = f"{field_context} {query}".lower()
    history_lower = _history_text(history).lower()
    if _is_casual_helper_message(query):
        return (
            "Hi. Ask me about this specific field and I will keep the answer scoped "
            "to what goes here, what format is expected, or what value is safest."
        )
    asks_meaning = any(
        phrase in normalized_query
        for phrase in [
            "what does that mean",
            "what does this mean",
            "what is that",
            "explain that",
            "explain this",
        ]
    )
    if asks_meaning and any(
        term in f"{history_lower} {normalized}"
        for term in ["h5", "tiff", "nifti", "zarr", "volume file", "directory/stack"]
    ):
        return (
            "Those are common ways microscopy image volumes are stored. "
            "`H5`, `TIFF`, `NIfTI`, and `Zarr` are file/container formats; a "
            "directory or stack means the volume is split across many files in a "
            "folder. For this field, pick whichever file or folder contains the raw "
            "image volume you want PyTC to read."
        )
    if "h5" in normalized_query or "hdf5" in normalized_query:
        return (
            "For H5/HDF5 data, choose the `.h5` or `.hdf5` file that contains the "
            "raw image volume. If the app later asks for an internal dataset name, "
            "use the dataset path inside that file, such as `/main` or `/raw`."
        )
    if "input image" in normalized or "dataset.input_path" in normalized:
        if not (
            _looks_like_initial_helper_prompt(query)
            or any(
                phrase in normalized_query
                for phrase in [
                    "what do i put",
                    "what should i put",
                    "where",
                    "choose",
                    "select",
                    "browse",
                    "help",
                ]
            )
        ):
            return None
        return (
            "Use the folder icon or Browse button to pick the image volume. "
            "Select a volume file for H5/TIFF/NIfTI/Zarr-style data, or select a "
            "folder when the dataset is stored as a directory/stack."
        )
    if "input label" in normalized or "dataset.label_name" in normalized:
        return (
            "Pick the matching label or mask volume for the image input. Use the "
            "same file/folder pattern as the image data so training pairs line up."
        )
    if "checkpoint" in normalized or "model.pre_model" in normalized:
        return (
            "Pick the trained model checkpoint file, usually a `.pth` or `.pth.tar` "
            "file. If you are starting from scratch, leave this unset until a model "
            "has been trained."
        )
    if "output path" in normalized:
        return (
            "Pick a folder where this run can write results. Use an empty or "
            "experiment-specific folder so predictions, logs, and intermediate files "
            "do not overwrite older work."
        )
    if "log path" in normalized or "solver.log_dir" in normalized:
        return (
            "Pick a folder for training logs and checkpoints. This should be writable "
            "and separate from raw image data."
        )
    if "aug_num" in normalized or "augment" in normalized:
        return (
            "`INFERENCE.AUG_NUM` controls how many test-time transformed predictions are "
            "averaged for inference. Use `4` for quick smoke runs; use `8` or `16` "
            "when you can spend more time for a more stable output. Higher values "
            "increase runtime substantially."
        )
    if "samples_per_batch" in normalized or "batch size" in normalized:
        return (
            "Batch size controls how many patches are processed at once. Keep it at "
            "`1` for large 3D volumes or memory-constrained runs; raise it only after "
            "a successful small run proves there is headroom."
        )
    if "blending" in normalized:
        return (
            "Blending controls how overlapping inference patches are combined. "
            "`gaussian` is usually the safer default because it softens patch-edge "
            "artifacts; use simpler blending only for quick debugging."
        )
    if "do_eval" in normalized or "eval mode" in normalized:
        return (
            "Eval mode asks the inference config to run evaluation-style behavior "
            "when matching labels/metrics are available. Leave it off for a plain "
            "prediction export unless you intentionally configured evaluation inputs."
        )
    return None


def _docs_only_helper_response(
    *,
    task_key: str,
    query: str,
    field_context: str,
    history: Optional[list] = None,
) -> str:
    direct = _direct_inline_help(query, field_context, history)
    if direct:
        return direct

    docs = _load_inline_help_docs()
    tokens = _helper_tokens(task_key, query, field_context, _history_text(history))
    scored: list[tuple[int, str, str]] = []
    for filename, content in docs.items():
        haystack = f"{filename}\n{content}".lower()
        score = sum(
            3 if token in filename.lower() else 1
            for token in tokens
            if token in haystack
        )
        if score > 0:
            scored.append((score, filename, content))
    scored.sort(key=lambda item: item[0], reverse=True)

    snippets = []
    for _, filename, content in scored[:2]:
        snippet = _extract_helper_snippet(content, tokens)
        if snippet:
            snippets.append(f"From `{filename}`:\n{snippet}")

    if snippets:
        joined = " ".join(
            line
            for snippet in snippets[:1]
            for line in snippet.splitlines()
            if line and not line.startswith("From `")
        )
        compact = re.sub(r"\s+", " ", joined).strip()
        if len(compact) > 360:
            compact = compact[:357].rstrip() + "..."
        return f"Relevant guidance: {compact}"
    return (
        "I could not find a precise local-doc match for this field. Use the visible "
        "YAML key and current value as the source of truth, and prefer a small smoke "
        "run before increasing runtime-heavy settings."
    )


def _should_use_docs_for_hybrid_helper(query: str, history: Optional[list]) -> bool:
    return _looks_like_initial_helper_prompt(query) or _is_casual_helper_message(query)


def _ensure_helper_chat(task_key: str):
    """Lazily build one helper agent, while keeping per-field histories."""
    global _chatbot_error
    if _SHARED_HELPER_CHAIN_KEY in _helper_chains:
        _helper_histories.setdefault(task_key, [])
        print(f"[CHATBOT] Reusing helper chain for task_key={task_key}")
        return True
    if build_helper_chain is None:
        print("[CHATBOT] build_helper_chain is unavailable")
        return False
    start_time = time.perf_counter()
    print(f"[CHATBOT] Initializing helper chain for task_key={task_key}...")
    try:
        agent, reset_fn = build_helper_chain()
        _helper_chains[_SHARED_HELPER_CHAIN_KEY] = (agent, reset_fn)
        _helper_histories[task_key] = []
        elapsed = time.perf_counter() - start_time
        print(f"[CHATBOT] Shared helper chain ready in {elapsed:.2f}s")
        return True
    except Exception as exc:
        _chatbot_error = exc
        print(
            "[CHATBOT] Failed to initialize helper LLM backend: "
            f"{exc.__class__.__name__}: {exc!r}"
        )
        traceback.print_exc()
        return False


@app.post("/chat/helper/query")
async def chat_helper_query(req: Request):
    request_id = request_id_from_request(req).replace("-", "")[:8]
    request_start = time.perf_counter()
    body = await req.json()
    task_key = body.get("taskKey")
    query = body.get("query")
    field_context = body.get("fieldContext", "")
    history = body.get("history") if isinstance(body.get("history"), list) else []

    if not task_key:
        raise HTTPException(status_code=400, detail="taskKey is required")
    if not isinstance(query, str) or not query.strip():
        raise HTTPException(status_code=400, detail="query must be a non-empty string.")
    print(
        f"[CHATBOT][{request_id}] Incoming /chat/helper/query "
        f"task_key={task_key} query_len={len(query.strip())}"
    )

    helper_mode = _inline_helper_mode()
    if helper_mode not in {"agent", "hybrid"} or (
        helper_mode == "hybrid" and _should_use_docs_for_hybrid_helper(query, history)
    ):
        print(
            f"[CHATBOT][{request_id}] Inline helper mode={helper_mode}:docs "
            f"task_key={task_key} field_context_len={len(str(field_context or ''))}"
        )
        response = _docs_only_helper_response(
            task_key=task_key,
            query=query,
            field_context=field_context,
            history=history,
        )
        log_request_summary(
            request_id=request_id,
            endpoint="/chat/helper/query",
            start_time=request_start,
            status="ok",
        )
        return {"response": response, "mode": "docs"}

    if not _ensure_helper_chat(task_key):
        print(
            f"[CHATBOT][{request_id}] Helper chain unavailable for task_key={task_key}"
        )
        log_request_summary(
            request_id=request_id,
            endpoint="/chat/helper/query",
            start_time=request_start,
            status="error",
            error_type="llm_unavailable",
        )
        raise HTTPException(
            status_code=503, detail=_llm_unavailable_detail(_chatbot_error)
        )

    agent, reset_fn = _helper_chains[_SHARED_HELPER_CHAIN_KEY]
    history = _helper_histories[task_key]

    # Prepend field context to the first message so the LLM knows what field
    # the user is looking at.
    user_content = (
        f"[Field context: {field_context}]\n\n{query}" if field_context else query
    )

    reset_fn()
    print(
        f"[CHATBOT][{request_id}] Inline helper mode={helper_mode} "
        f"history_len={len(history)}; invoking helper "
        f"with context_len={len(user_content)}"
    )
    all_messages = history + [{"role": "user", "content": user_content}]
    try:
        result = _invoke_with_progress(
            lambda: agent.invoke({"messages": all_messages}),
            label="helper chain invoke",
            request_id=request_id,
        )
    except Exception as exc:
        print(
            "[CHATBOT] Helper LLM request failed: " f"{exc.__class__.__name__}: {exc!r}"
        )
        traceback.print_exc()
        log_request_summary(
            request_id=request_id,
            endpoint="/chat/helper/query",
            start_time=request_start,
            status="error",
            error_type=exc.__class__.__name__,
        )
        raise HTTPException(
            status_code=503, detail=_llm_unavailable_detail(exc)
        ) from exc
    messages = result.get("messages", [])
    response = messages[-1].content if messages else "No response generated"
    response = _compact_agent_response(response, max_words=80)
    response = _sanitize_agent_response(response)
    history.append({"role": "user", "content": user_content})
    history.append({"role": "assistant", "content": response})
    total_elapsed = time.perf_counter() - request_start
    print(
        f"[CHATBOT][{request_id}] /chat/helper/query completed in {total_elapsed:.2f}s "
        f"response_len={len(response) if isinstance(response, str) else 0}"
    )
    log_request_summary(
        request_id=request_id,
        endpoint="/chat/helper/query",
        start_time=request_start,
        status="ok",
    )
    return {"response": response}


@app.post("/chat/helper/clear")
async def chat_helper_clear(req: Request):
    body = await req.json()
    task_key = body.get("taskKey")
    if task_key and task_key in _helper_histories:
        _helper_histories[task_key].clear()
    return {"message": "Helper chat cleared"}


def run():
    log_path = configure_process_logging("server_api")
    print(f"[APP LOG] Writing app events to {log_path}")
    uvicorn.run(
        app,
        host=PYTC_API_HOST,
        port=PYTC_API_PORT,
        reload=False,  # Temporarily disabled to force fresh load
        log_level="info",
    )


if __name__ == "__main__":
    run()
