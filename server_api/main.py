import json
import logging
import pathlib
import re
import shutil
import tempfile
import traceback
import time
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
from server_api.workflows.db_models import WorkflowEvent
from server_api.workflows.service import (
    append_event_for_workflow_if_present,
    decode_json,
    get_user_workflow_or_404,
    update_workflow_fields,
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


REACT_APP_SERVER_PROTOCOL = "http"
REACT_APP_SERVER_URL = "localhost:4243"

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
_ensure_sqlite_column("chat_messages", "actions_json", "actions_json TEXT")
_ensure_sqlite_column("chat_messages", "commands_json", "commands_json TEXT")
_ensure_sqlite_column("chat_messages", "proposals_json", "proposals_json TEXT")

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


@app.on_event("startup")
async def configure_app_event_logging():
    log_path = configure_process_logging("server_api")
    logger.info("App event logging enabled at %s", log_path)


@app.middleware("http")
async def log_http_requests(request: Request, call_next):
    request_id = request_id_from_request(request)
    start_time = time.perf_counter()
    path = request.url.path
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
    return f"{scheme}://{hostname}:4244"


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
    try:
        response = requests.request(
            method=method,
            url=target_url,
            json=json_body,
            params=params,
            timeout=timeout,
        )
    except requests.exceptions.ConnectionError as exc:
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
        raise HTTPException(
            status_code=504,
            detail={
                "message": "PyTC worker request timed out.",
                "worker_url": target_url,
                "error": "Timeout",
            },
        ) from exc
    except requests.RequestException as exc:
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
        raise HTTPException(
            status_code=response.status_code,
            detail={
                "message": "PyTC worker returned an error.",
                "worker_url": target_url,
                "upstream_status": response.status_code,
                "upstream_body": payload,
            },
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


def _resolve_requested_config(path: str) -> Optional[pathlib.Path]:
    if not path:
        return None

    normalized = path.replace("\\", "/").strip()
    if not normalized or normalized.startswith("/"):
        return None
    if ".." in pathlib.PurePosixPath(normalized).parts:
        return None

    candidates = [(PYTC_ROOT / normalized).resolve()]
    for root in _iter_existing_config_roots():
        candidates.append((root / normalized).resolve())

    for candidate in candidates:
        if _is_valid_config_path(candidate):
            return candidate
    return None


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
    canonical_path = str(requested.relative_to(PYTC_ROOT)).replace("\\", "/")
    return {"path": canonical_path, "content": content}


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
                raise ValueError(
                    "Failed to derive a 3D segmentation preview from the "
                    f"2-channel prediction volume: {exc}"
                ) from exc
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
            image = process_path(payload["image"])
            label = process_path(payload.get("label"))
            scales = payload["scales"]
            workflow_id = payload.get("workflow_id") or payload.get("workflowId")

        print(image, label, scales)

        if image is None:
            raise HTTPException(
                status_code=400, detail="Image path or file is required."
            )
        if not pathlib.Path(image).exists():
            _raise_missing_volume_error(pathlib.Path(image), "image")
        if label is not None and not pathlib.Path(label).exists():
            _raise_missing_volume_error(pathlib.Path(label), "label")

        # neuroglancer setting -- bind to this to make accessible outside of container
        ip = "0.0.0.0"
        port = 4244
        neuroglancer.set_server_bind_address(ip, port)
        viewer = neuroglancer.Viewer()
        # Neuroglancer expects the EM volume axes in z, y, x order.
        res = neuroglancer.CoordinateSpace(
            names=["z", "y", "x"], units=["nm", "nm", "nm"], scales=scales
        )
        try:
            im = readVol(image, image_type="im")
        except Exception as e:
            raise HTTPException(
                status_code=400, detail=f"Failed to read image volume: {str(e)}"
            )
        try:
            gt = readVol(label, image_type="seg") if label else None
            if gt is not None:
                gt = _normalize_segmentation_volume_for_neuroglancer(gt)
        except Exception as e:
            raise HTTPException(
                status_code=400, detail=f"Failed to prepare label volume: {str(e)}"
            )

        def ngLayer(data, res, oo=[0, 0, 0], tt="segmentation"):
            try:
                return neuroglancer.LocalVolume(
                    data, dimensions=res, volume_type=tt, voxel_offset=oo
                )
            except Exception as exc:
                raise HTTPException(
                    status_code=400,
                    detail=f"Failed to prepare Neuroglancer {tt} layer: {exc}",
                ) from exc

        with viewer.txn() as s:
            s.layers.append(name="im", layer=ngLayer(im, res, tt="image"))
            if gt is not None:
                s.layers.append(name="gt", layer=ngLayer(gt, res, tt="segmentation"))

        public_url = _build_neuroglancer_public_url(str(viewer), req)
        if workflow_id:
            workflow = get_user_workflow_or_404(
                db, workflow_id=int(workflow_id), user_id=current_user.id
            )
            update_workflow_fields(
                db,
                workflow,
                {
                    "stage": "visualization",
                    "image_path": str(image),
                    "label_path": str(label) if label else None,
                    "neuroglancer_url": public_url,
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
                    "image_path": str(image),
                    "label_path": str(label) if label else None,
                    "scales": scales,
                    "neuroglancer_url": public_url,
                },
            )
        print(public_url)
        return public_url
    finally:
        for path in cleanup_paths:
            try:
                path.unlink()
            except FileNotFoundError:
                pass
            except PermissionError:
                pass


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
    if not _ensure_chatbot():
        print(f"[CHATBOT][{request_id}] Main chain unavailable before request")
        log_request_summary(
            request_id=request_id,
            endpoint="/chat/query",
            start_time=request_start,
            status="error",
            error_type="llm_unavailable",
        )
        raise HTTPException(
            status_code=503, detail=_llm_unavailable_detail(_chatbot_error)
        )
    body = await req.json()
    query = body.get("query")
    convo_id = body.get("conversationId")
    if not isinstance(query, str) or not query.strip():
        raise HTTPException(status_code=400, detail="Query must be a non-empty string.")
    print(
        f"[CHATBOT][{request_id}] Parsed request: convo_id={convo_id}, "
        f"query_len={len(query.strip())}"
    )

    # Auto-create a conversation if none supplied
    if not convo_id:
        convo = models.Conversation(user_id=user.id, title="New Chat")
        db.add(convo)
        db.commit()
        db.refresh(convo)
        convo_id = convo.id
    else:
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
        log_request_summary(
            request_id=request_id,
            endpoint="/chat/query",
            start_time=request_start,
            status="error",
            error_type=exc.__class__.__name__,
        )
        raise HTTPException(
            status_code=503, detail=_llm_unavailable_detail(exc)
        ) from exc
    messages = result.get("messages", [])
    response = messages[-1].content if messages else "No response generated"
    response = _compact_agent_response(response)
    response = _sanitize_agent_response(response)
    print(
        f"[CHATBOT][{request_id}] Chain returned messages={len(messages)}, "
        f"response_len={len(response) if isinstance(response, str) else 0}"
    )

    # Persist to DB
    db.add(models.ChatMessage(conversation_id=convo_id, role="user", content=query))
    db.add(
        models.ChatMessage(conversation_id=convo_id, role="assistant", content=response)
    )

    # Auto-title: first user message becomes the title (truncated)
    if convo.title == "New Chat":
        convo.title = query[:120].strip() or "New Chat"
    convo.updated_at = datetime.now(timezone.utc)

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

    return {"response": response, "conversationId": convo_id}


@app.post("/chat/clear")
async def clear_chat(
    user: models.User = Depends(get_current_user),
):
    """Reset the in-memory LangChain context (does NOT delete DB messages)."""
    global _active_convo_id, _chat_history
    if not _ensure_chatbot():
        detail = "Chatbot is not configured"
        if "_chatbot_error" in globals():
            detail = f"{detail}: {_chatbot_error}"
        raise HTTPException(status_code=503, detail=detail)
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


def _direct_inline_help(query: str, field_context: str) -> Optional[str]:
    normalized = f"{field_context} {query}".lower()
    if "input image" in normalized or "dataset.input_path" in normalized:
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


def _docs_only_helper_response(*, task_key: str, query: str, field_context: str) -> str:
    direct = _direct_inline_help(query, field_context)
    if direct:
        return direct

    docs = _load_inline_help_docs()
    tokens = _helper_tokens(task_key, query, field_context)
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


def _ensure_helper_chat(task_key: str):
    """Lazily build a helper agent for *task_key*, reusing it on subsequent calls."""
    global _chatbot_error
    if task_key in _helper_chains:
        print(f"[CHATBOT] Reusing helper chain for task_key={task_key}")
        return True
    if build_helper_chain is None:
        print("[CHATBOT] build_helper_chain is unavailable")
        return False
    start_time = time.perf_counter()
    print(f"[CHATBOT] Initializing helper chain for task_key={task_key}...")
    try:
        agent, reset_fn = build_helper_chain()
        _helper_chains[task_key] = (agent, reset_fn)
        _helper_histories[task_key] = []
        elapsed = time.perf_counter() - start_time
        print(f"[CHATBOT] Helper chain ready for task_key={task_key} in {elapsed:.2f}s")
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

    if not task_key:
        raise HTTPException(status_code=400, detail="taskKey is required")
    if not isinstance(query, str) or not query.strip():
        raise HTTPException(status_code=400, detail="query must be a non-empty string.")
    print(
        f"[CHATBOT][{request_id}] Incoming /chat/helper/query "
        f"task_key={task_key} query_len={len(query.strip())}"
    )

    if _inline_helper_mode() != "agent":
        response = _docs_only_helper_response(
            task_key=task_key,
            query=query,
            field_context=field_context,
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

    agent, reset_fn = _helper_chains[task_key]
    history = _helper_histories[task_key]

    # Prepend field context to the first message so the LLM knows what field
    # the user is looking at.
    user_content = (
        f"[Field context: {field_context}]\n\n{query}" if field_context else query
    )

    reset_fn()
    print(
        f"[CHATBOT][{request_id}] Helper history_len={len(history)}; invoking helper "
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
        host="0.0.0.0",
        port=4242,
        reload=False,  # Temporarily disabled to force fresh load
        log_level="info",
    )


if __name__ == "__main__":
    run()
