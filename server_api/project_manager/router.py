"""
Project Manager — FastAPI router  (v2 — Industrial Grade)

Endpoints
---------
GET  /api/pm/config                   Active metadata/storage configuration
POST /api/pm/config                   Update active metadata/storage configuration
GET  /api/pm/schema                   Human-readable schema + starter template
GET  /api/pm/data                     Full PM state + computed global_progress
POST /api/pm/data                     Overwrite full state (bulk save)
POST /api/pm/data/reset               Reset to a fresh project state
GET  /api/pm/volumes                  Paginated volume list with optional filters
PATCH /api/pm/volumes/{volume_id}     Update a single volume's status/assignee
"""

import os
import sys
import json
import math
import pathlib
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel

from server_api.project_manager.template import (
    PROJECT_MANAGER_WORKERS,
    VALID_VOLUME_STATUSES,
    build_default_users,
    build_empty_state,
    build_schema_reference,
)

router = APIRouter()

# ── Paths ─────────────────────────────────────────────────────────────────────
_HERE = pathlib.Path(__file__).resolve().parent
_API_DIR = _HERE.parent
_DATA_DIR = _API_DIR / "data_store"
_PROJECT_ROOT = _API_DIR.parent.resolve()
DEFAULT_DATA_PATH = (_DATA_DIR / "project_manager_data.json").resolve()
DEFAULT_DATA_ROOT = _PROJECT_ROOT

# Dynamic config via environment variables
DEFAULT_DATA_FILE = str(DEFAULT_DATA_PATH)
_DATA_FILE_OVERRIDE: Optional[str] = None
_DATA_ROOT_OVERRIDE: Optional[str] = None


def _normalize_path(path_str: str, *, base: pathlib.Path) -> pathlib.Path:
    path = pathlib.Path(path_str).expanduser()
    if not path.is_absolute():
        path = base / path
    return path.resolve()


def get_data_file_path() -> pathlib.Path:
    global _DATA_FILE_OVERRIDE
    if _DATA_FILE_OVERRIDE:
        return pathlib.Path(_DATA_FILE_OVERRIDE)
    path_str = os.environ.get("PROJECT_METADATA_JSON")
    if path_str:
        return _normalize_path(path_str, base=_PROJECT_ROOT)
    return DEFAULT_DATA_PATH


def get_data_root() -> pathlib.Path:
    global _DATA_ROOT_OVERRIDE
    if _DATA_ROOT_OVERRIDE:
        return pathlib.Path(_DATA_ROOT_OVERRIDE)
    root_str = os.environ.get("DATA_ROOT_EM", "")
    if not root_str:
        return DEFAULT_DATA_ROOT
    return _normalize_path(root_str, base=_PROJECT_ROOT)


# ── Worker definitions (single source of truth) ───────────────────────────────
_WORKERS = [dict(worker) for worker in PROJECT_MANAGER_WORKERS]
_WORKER_KEYS = [w["key"] for w in _WORKERS]  # ["alex","jordan","taylor","morgan"]
# ── Helpers ───────────────────────────────────────────────────────────────────


def _ensure_data_dir() -> None:
    _DATA_DIR.mkdir(parents=True, exist_ok=True)


def _read_project_info_preview(file_path: pathlib.Path) -> Optional[Dict[str, Any]]:
    if not file_path.exists():
        return None
    try:
        payload = json.loads(file_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    project_info = payload.get("project_info")
    return project_info if isinstance(project_info, dict) else None


def _get_pm_config_snapshot() -> Dict[str, Any]:
    file_path = get_data_file_path()
    data_root = get_data_root()
    project_info = _read_project_info_preview(file_path)
    project_name = (
        (project_info or {}).get("name")
        or file_path.stem.replace("_", " ").strip()
        or "Project"
    )
    return {
        "project_name": project_name,
        "project_info": project_info,
        "metadata_path": str(file_path),
        "default_metadata_path": str(DEFAULT_DATA_PATH),
        "using_metadata_override": file_path != DEFAULT_DATA_PATH,
        "metadata_exists": file_path.exists(),
        "data_root": str(data_root),
        "default_data_root": str(DEFAULT_DATA_ROOT),
        "using_data_root_override": data_root != DEFAULT_DATA_ROOT,
        "data_root_exists": data_root.exists(),
        "data_root_is_dir": data_root.is_dir(),
    }


def _read_data() -> Dict[str, Any]:
    file_path = get_data_file_path()
    project_name = file_path.stem.replace("_", " ").strip() or "New Project"
    # Ensure parent directory exists for the default file
    if file_path == pathlib.Path(DEFAULT_DATA_FILE):
        _ensure_data_dir()

    if not file_path.exists():
        empty_state = build_empty_state(
            project_name=project_name.title(),
            description="No storage synced yet.",
        )
        _write_data(empty_state)
        return empty_state
    try:
        return json.loads(file_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise HTTPException(
            status_code=500, detail=f"Failed to read data store: {exc}"
        ) from exc


def _write_data(payload: Dict[str, Any]) -> None:
    file_path = get_data_file_path()
    if file_path == pathlib.Path(DEFAULT_DATA_FILE):
        _ensure_data_dir()

    tmp = file_path.with_suffix(".tmp")
    try:
        tmp.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        tmp.replace(file_path)
    except OSError as exc:
        raise HTTPException(
            status_code=500, detail=f"Failed to write data store: {exc}"
        ) from exc


def _compute_global_progress(volumes: List[Dict[str, Any]]) -> Dict[str, Any]:
    total = len(volumes)
    done = sum(1 for v in volumes if v["status"] == "done")
    in_progress = sum(1 for v in volumes if v["status"] == "in_progress")
    todo = total - done - in_progress
    pct = round((done / total) * 100, 1) if total else 0
    # Per-worker breakdown
    by_worker: Dict[str, Dict[str, int]] = {}
    for wk in _WORKER_KEYS:
        subset = [v for v in volumes if v["assignee"] == wk]
        w_done = sum(1 for v in subset if v["status"] == "done")
        w_ip = sum(1 for v in subset if v["status"] == "in_progress")
        by_worker[wk] = {
            "total": len(subset),
            "done": w_done,
            "in_progress": w_ip,
            "todo": len(subset) - w_done - w_ip,
            "pct": round((w_done / len(subset)) * 100, 1) if subset else 0,
        }
    return {
        "total": total,
        "done": done,
        "in_progress": in_progress,
        "todo": todo,
        "pct": pct,
        "by_worker": by_worker,
    }


# ── Pydantic models ───────────────────────────────────────────────────────────


class VolumeUpdate(BaseModel):
    status: Optional[str] = None  # todo | in_progress | done
    assignee: Optional[str] = None


class LoginRequest(BaseModel):
    username: str
    password: str


class LinkMetadataRequest(BaseModel):
    path: str


class ProjectConfigUpdateRequest(BaseModel):
    metadata_path: Optional[str] = None
    data_root: Optional[str] = None


# ── Endpoints ─────────────────────────────────────────────────────────────────


@router.post("/login")
async def login(body: LoginRequest):
    """Simple credential matching for Project Manager login."""
    data = _read_data()
    users = data.get("users", [])

    for user in users:
        if user["username"] == body.username and user["password"] == body.password:
            # Return user metadata without password
            return {
                "ok": True,
                "user": {
                    "username": user["username"],
                    "name": user["name"],
                    "role": user["role"],
                    "key": user["key"],
                },
            }

    raise HTTPException(status_code=401, detail="Invalid username or password")


@router.get("/config")
def get_pm_config():
    return _get_pm_config_snapshot()


@router.post("/config")
async def update_pm_config(body: ProjectConfigUpdateRequest):
    global _DATA_FILE_OVERRIDE, _DATA_ROOT_OVERRIDE
    provided_fields = getattr(body, "model_fields_set", set()) or getattr(
        body, "__fields_set__", set()
    )

    if "metadata_path" in provided_fields:
        raw_metadata_path = (body.metadata_path or "").strip()
        if not raw_metadata_path:
            _DATA_FILE_OVERRIDE = None
        else:
            candidate = _normalize_path(raw_metadata_path, base=_PROJECT_ROOT)
            if candidate.exists() and candidate.is_dir():
                raise HTTPException(
                    status_code=400,
                    detail="Metadata path must point to a JSON file, not a directory.",
                )
            if not candidate.exists() and not candidate.parent.exists():
                raise HTTPException(
                    status_code=400,
                    detail="Metadata file parent directory does not exist.",
                )
            _DATA_FILE_OVERRIDE = str(candidate)

    if "data_root" in provided_fields:
        raw_data_root = (body.data_root or "").strip()
        if not raw_data_root:
            _DATA_ROOT_OVERRIDE = None
        else:
            candidate = _normalize_path(raw_data_root, base=_PROJECT_ROOT)
            if not candidate.exists() or not candidate.is_dir():
                raise HTTPException(
                    status_code=400,
                    detail="Data root must be an existing directory.",
                )
            _DATA_ROOT_OVERRIDE = str(candidate)

    return _get_pm_config_snapshot()


@router.get("/schema")
def get_pm_schema():
    return build_schema_reference()


@router.get("/data")
def get_pm_data():
    """Return full PM state + computed global_progress (volumes excluded from body)."""
    data = _read_data()
    volumes = data.get("volumes", [])
    # Attach computed progress but omit the large volumes array from this response
    # (volumes are served via /api/pm/volumes with pagination)
    result = {k: v for k, v in data.items() if k != "volumes"}
    result["global_progress"] = _compute_global_progress(volumes)
    return result


@router.post("/data")
async def save_pm_data(req: Request):
    """Overwrite the PM state (bulk save from frontend debounced write)."""
    try:
        payload = await req.json()
    except Exception as exc:
        raise HTTPException(
            status_code=400, detail=f"Invalid JSON body: {exc}"
        ) from exc
    # Preserve volumes from current file if payload doesn't include them
    current = _read_data()
    if "volumes" not in payload:
        payload["volumes"] = current.get("volumes", [])
    _write_data(payload)
    return {"ok": True}


@router.post("/data/ingest")
async def ingest_data():
    """Trigger the real-world data ingestion script."""
    data_root = get_data_root()
    json_path = get_data_file_path()

    import subprocess

    script_path = _API_DIR.parent / "scripts" / "ingest_data.py"

    env = os.environ.copy()
    env["DATA_ROOT_EM"] = str(data_root)
    env["PROJECT_METADATA_JSON"] = str(json_path)

    try:
        result = subprocess.run(
            [sys.executable, str(script_path)],
            env=env,
            capture_output=True,
            text=True,
            check=True,
        )
        # Reload and return the updated data
        updated_data = _read_data()
        return {
            "ok": True,
            "message": "Ingestion successful",
            "output": result.stdout,
            "data": updated_data,
        }
    except subprocess.CalledProcessError as e:
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {e.stderr}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")


@router.post("/data/reset")
def reset_pm_data():
    """Reset the active metadata file to a fresh project state."""
    file_path = get_data_file_path()
    project_name = file_path.stem.replace("_", " ").strip().title() or "New Project"
    empty_state = build_empty_state(
        project_name=project_name,
        description="No storage synced yet.",
    )
    _write_data(empty_state)
    result = {k: v for k, v in empty_state.items() if k != "volumes"}
    result["global_progress"] = _compute_global_progress(empty_state["volumes"])
    return result


@router.post("/data/link")
async def link_metadata(body: LinkMetadataRequest):
    """Dynamically link to an external metadata JSON file for the current session."""
    candidate = _normalize_path(body.path, base=_PROJECT_ROOT)
    if candidate.exists() and candidate.is_dir():
        raise HTTPException(
            status_code=400,
            detail="Metadata path must point to a JSON file, not a directory.",
        )
    if not candidate.exists() and not candidate.parent.exists():
        raise HTTPException(
            status_code=400,
            detail="Metadata file parent directory does not exist.",
        )
    global _DATA_FILE_OVERRIDE
    _DATA_FILE_OVERRIDE = str(candidate)
    snapshot = _get_pm_config_snapshot()
    return {"ok": True, "active_path": _DATA_FILE_OVERRIDE, "config": snapshot}


# ── Volume endpoints ──────────────────────────────────────────────────────────


@router.get("/volumes")
def get_volumes(
    assignee: Optional[str] = Query(None, description="Filter by worker key"),
    status: Optional[str] = Query(
        None, description="Filter by status: todo|in_progress|done"
    ),
    id: Optional[str] = Query(None, description="Exact filename/task ID match"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    """Return paginated volume list with optional assignee/status filters."""
    data = _read_data()
    volumes: List[Dict[str, Any]] = data.get("volumes", [])

    # Apply filters
    if id:
        volumes = [v for v in volumes if v["id"] == id]
    if assignee:
        volumes = [v for v in volumes if v["assignee"] == assignee]
    if status:
        volumes = [v for v in volumes if v["status"] == status]

    total = len(volumes)
    total_pages = max(1, math.ceil(total / page_size))
    start = (page - 1) * page_size
    items = volumes[start : start + page_size]

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
        "items": items,
    }


@router.patch("/volumes/{volume_id}")
async def update_volume_status(volume_id: str, body: VolumeUpdate):
    """Update a single volume's status and/or assignee atomically."""
    provided_fields = getattr(body, "model_fields_set", set()) or getattr(
        body, "__fields_set__", set()
    )
    if not provided_fields:
        raise HTTPException(
            status_code=400, detail="Provide at least one of: status, assignee."
        )

    valid_statuses = set(VALID_VOLUME_STATUSES)
    if "status" in provided_fields and body.status not in valid_statuses:
        raise HTTPException(
            status_code=400, detail=f"status must be one of {valid_statuses}"
        )
    if "assignee" in provided_fields and body.assignee not in {*_WORKER_KEYS, None}:
        raise HTTPException(
            status_code=400,
            detail=f"assignee must be one of {_WORKER_KEYS} or null",
        )

    data = _read_data()
    volumes: List[Dict[str, Any]] = data.get("volumes", [])

    for vol in volumes:
        if vol["id"] == volume_id:
            if "status" in provided_fields:
                vol["status"] = body.status
            if "assignee" in provided_fields:
                vol["assignee"] = body.assignee
            data["volumes"] = volumes
            _write_data(data)
            return {
                "ok": True,
                "volume": vol,
                "global_progress": _compute_global_progress(volumes),
            }

    raise HTTPException(status_code=404, detail=f"Volume '{volume_id}' not found")


@router.get("/workers")
def get_workers():
    """Return the list of defined workers."""
    return {"workers": _WORKERS}
