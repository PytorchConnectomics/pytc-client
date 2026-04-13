"""
Project Manager — FastAPI router  (v2 — Industrial Grade)

Endpoints
---------
GET  /api/pm/data                     Full PM state + computed global_progress
POST /api/pm/data                     Overwrite full state (bulk save)
POST /api/pm/data/reset               Revert to seed data
GET  /api/pm/volumes                  Paginated volume list with optional filters
PATCH /api/pm/volumes/{volume_id}     Update a single volume's status
"""

from __future__ import annotations

import json
import math
import pathlib
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel

router = APIRouter()

# ── Paths ─────────────────────────────────────────────────────────────────────
_HERE = pathlib.Path(__file__).resolve().parent
_API_DIR = _HERE.parent
_DATA_DIR = _API_DIR / "data_store"
_DATA_FILE = _DATA_DIR / "project_manager_data.json"

# ── Worker definitions (single source of truth) ───────────────────────────────
_WORKERS = [
    {"key": "alex", "name": "Alex Rivera", "avatarColor": "#1890ff"},
    {"key": "jordan", "name": "Jordan Smith", "avatarColor": "#52c41a"},
    {"key": "taylor", "name": "Sam Taylor", "avatarColor": "#fadb14"},
    {"key": "morgan", "name": "Morgan Lee", "avatarColor": "#eb2f96"},
]
_WORKER_KEYS = [w["key"] for w in _WORKERS]  # ["alex","jordan","taylor","morgan"]
VOLUMES_PER_WORKER = 250
TOTAL_VOLUMES = len(_WORKER_KEYS) * VOLUMES_PER_WORKER  # 1 000


def _generate_volumes() -> List[Dict[str, Any]]:
    """Return 1 000 volume records distributed evenly across 4 workers."""
    vols: List[Dict[str, Any]] = []
    for idx in range(1, TOTAL_VOLUMES + 1):
        worker_key = _WORKER_KEYS[(idx - 1) // VOLUMES_PER_WORKER]
        vols.append(
            {
                "id": f"vol_{idx:03d}_em.h5",
                "filename": f"vol_{idx:03d}_em.h5",
                "assignee": worker_key,
                "status": "todo",  # todo | in_progress | done
            }
        )
    return vols


# ── Seed Data ─────────────────────────────────────────────────────────────────
def _build_seed() -> Dict[str, Any]:
    return {
        # ── Volume catalogue ──────────────────────────────────────────────────
        "volumes": _generate_volumes(),
        # ── Weekly quota table (one row per worker) ───────────────────────────
        "quota_data": [
            {
                "key": "1",
                "name": "Alex Rivera",
                "worker_key": "alex",
                "datasets": ["Hippocampus_CA3", "Motor_Cortex_M1"],
                "mon": 300,
                "tue": 300,
                "wed": 300,
                "thu": 300,
                "fri": 300,
                "sat": 150,
                "sun": 100,
                "actualMon": 310,
                "actualTue": 290,
                "actualWed": 320,
                "actualThu": 280,
                "actualFri": 300,
                "actualSat": 160,
                "actualSun": 90,
            },
            {
                "key": "2",
                "name": "Jordan Smith",
                "worker_key": "jordan",
                "datasets": ["Cerebellum_PC"],
                "mon": 250,
                "tue": 250,
                "wed": 250,
                "thu": 250,
                "fri": 250,
                "sat": 0,
                "sun": 0,
                "actualMon": 240,
                "actualTue": 260,
                "actualWed": 230,
                "actualThu": 250,
                "actualFri": 220,
                "actualSat": 0,
                "actualSun": 0,
            },
            {
                "key": "3",
                "name": "Sam Taylor",
                "worker_key": "taylor",
                "datasets": ["Retina_GCL"],
                "mon": 200,
                "tue": 200,
                "wed": 200,
                "thu": 200,
                "fri": 200,
                "sat": 250,
                "sun": 250,
                "actualMon": 180,
                "actualTue": 190,
                "actualWed": 170,
                "actualThu": 210,
                "actualFri": 200,
                "actualSat": 100,
                "actualSun": 0,
            },
            {
                "key": "4",
                "name": "Morgan Lee",
                "worker_key": "morgan",
                "datasets": ["Visual_Cortex_V1"],
                "mon": 240,
                "tue": 240,
                "wed": 240,
                "thu": 240,
                "fri": 240,
                "sat": 0,
                "sun": 0,
                "actualMon": 250,
                "actualTue": 260,
                "actualWed": 270,
                "actualThu": 240,
                "actualFri": 230,
                "actualSat": 0,
                "actualSun": 0,
            },
        ],
        # ── Proofreader progress cards (one per worker) ───────────────────────
        "proofreader_data": [
            {
                "key": "1",
                "name": "Alex Rivera",
                "worker_key": "alex",
                "avatarColor": "#1890ff",
                "role": "Senior Annotator",
                "totalPoints": 12450,
                "weeklyPoints": 1420,
                "weeklyQuota": 1750,
                "accuracy": 98.5,
                "lastActive": "2 mins ago",
                "status": "online",
            },
            {
                "key": "2",
                "name": "Jordan Smith",
                "worker_key": "jordan",
                "avatarColor": "#52c41a",
                "role": "Proofreader",
                "totalPoints": 8900,
                "weeklyPoints": 1100,
                "weeklyQuota": 1500,
                "accuracy": 94.2,
                "lastActive": "15 mins ago",
                "status": "online",
            },
            {
                "key": "3",
                "name": "Sam Taylor",
                "worker_key": "taylor",
                "avatarColor": "#fadb14",
                "role": "Proofreader",
                "totalPoints": 5600,
                "weeklyPoints": 850,
                "weeklyQuota": 1500,
                "accuracy": 92.1,
                "lastActive": "1 hour ago",
                "status": "away",
            },
            {
                "key": "4",
                "name": "Morgan Lee",
                "worker_key": "morgan",
                "avatarColor": "#eb2f96",
                "role": "Junior Annotator",
                "totalPoints": 3200,
                "weeklyPoints": 1250,
                "weeklyQuota": 1200,
                "accuracy": 96.8,
                "lastActive": "3 hours ago",
                "status": "offline",
            },
        ],
        # ── Team throughput (last 7 days) ─────────────────────────────────────
        "throughput_data": [
            {"day": "Mon", "count": 4200},
            {"day": "Tue", "count": 3800},
            {"day": "Wed", "count": 5100},
            {"day": "Thu", "count": 4700},
            {"day": "Fri", "count": 5300},
            {"day": "Sat", "count": 1200},
            {"day": "Sun", "count": 900},
        ],
        # ── Dashboard datasets ────────────────────────────────────────────────
        "datasets": [
            {
                "key": "1",
                "name": "Hippocampus_CA3",
                "experiment": "Synapse detection",
                "total": 12450,
                "proofread": 38,
                "status": "in_progress",
                "eta": "Jan 18",
                "priority": "high",
            },
            {
                "key": "2",
                "name": "Motor_Cortex_M1",
                "experiment": "Axon tracing",
                "total": 9800,
                "proofread": 72,
                "status": "in_progress",
                "eta": "Jan 22",
                "priority": "high",
            },
            {
                "key": "3",
                "name": "Cerebellum_PC",
                "experiment": "Dendrite segmentation",
                "total": 6200,
                "proofread": 91,
                "status": "done",
                "eta": "Complete",
                "priority": "normal",
            },
            {
                "key": "4",
                "name": "Retina_GCL",
                "experiment": "Cell classification",
                "total": 3300,
                "proofread": 5,
                "status": "blocked",
                "eta": "TBD",
                "priority": "high",
            },
            {
                "key": "5",
                "name": "Olfactory_Bulb",
                "experiment": "Glomeruli mapping",
                "total": 7650,
                "proofread": 0,
                "status": "not_started",
                "eta": "Feb 28",
                "priority": "normal",
            },
            {
                "key": "6",
                "name": "Visual_Cortex_V1",
                "experiment": "Spine detection",
                "total": 15000,
                "proofread": 55,
                "status": "in_progress",
                "eta": "Feb 10",
                "priority": "normal",
            },
        ],
        # ── Timeline / chart data ─────────────────────────────────────────────
        "milestones": [
            {"label": "Model v1", "date": "2025-11-15", "color": "#1890ff"},
            {"label": "Mid-Review", "date": "2025-12-20", "color": "#722ed1"},
            {"label": "Model v2", "date": "2026-01-28", "color": "#1890ff"},
            {"label": "Data Freeze", "date": "2026-02-15", "color": "#fa8c16"},
            {"label": "Model v3", "date": "2026-03-20", "color": "#1890ff"},
        ],
        "cumulative_data": [
            0,
            480,
            1100,
            1950,
            2800,
            3900,
            5100,
            6200,
            7450,
            8600,
            9900,
            11200,
            12600,
            13900,
            15400,
            17000,
            18500,
            20100,
            21800,
            23400,
            25000,
            26700,
            28500,
            30200,
            32000,
            33800,
        ],
        "cumulative_target": [
            0,
            600,
            1200,
            1800,
            2400,
            3000,
            3600,
            4800,
            6000,
            7200,
            8400,
            9600,
            10800,
            12000,
            13200,
            14400,
            15600,
            16800,
            18000,
            19200,
            20400,
            21600,
            22800,
            24000,
            25200,
            26400,
        ],
        "at_risk": [
            {
                "label": "Hippocampus_CA3",
                "reason": "Low progress (38%)",
                "icon": "progress",
            },
            {
                "label": "Motor_Cortex_M1",
                "reason": "Deadline approaching",
                "icon": "clock",
            },
            {
                "label": "Retina_GCL",
                "reason": "Blocked — awaiting data",
                "icon": "blocked",
            },
        ],
        "upcoming_milestones": [
            {"label": "Model v2 data freeze", "date": "JAN 28"},
            {"label": "Mid-project review", "date": "FEB 5"},
            {"label": "Final data freeze", "date": "FEB 15"},
            {"label": "Model v3 launch", "date": "MAR 20"},
        ],
        "msg_preview": (
            "Hi Team,\n\nI've just assigned the quotas for the upcoming week. "
            "Please review your targets in the dashboard. Our goal for this week "
            "is to maintain 95%+ accuracy while meeting the sample volume targets.\n\nGood luck!"
        ),
        # Workers list (mirrors _WORKERS, stored so frontend can read it)
        "workers": _WORKERS,
        # ── Users for login ───────────────────────────────────────────────────
        "users": [
            {
                "username": "admin",
                "password": "admin123",
                "name": "Project Manager",
                "role": "admin",
                "key": "admin",
            },
            {
                "username": "alex",
                "password": "alex123",
                "name": "Alex Rivera",
                "role": "worker",
                "key": "alex",
            },
            {
                "username": "jordan",
                "password": "jordan123",
                "name": "Jordan Smith",
                "role": "worker",
                "key": "jordan",
            },
            {
                "username": "taylor",
                "password": "taylor123",
                "name": "Sam Taylor",
                "role": "worker",
                "key": "taylor",
            },
            {
                "username": "morgan",
                "password": "morgan123",
                "name": "Morgan Lee",
                "role": "worker",
                "key": "morgan",
            },
        ],
    }


_SEED: Dict[str, Any] = _build_seed()


# ── Helpers ───────────────────────────────────────────────────────────────────


def _ensure_data_dir() -> None:
    _DATA_DIR.mkdir(parents=True, exist_ok=True)


def _read_data() -> Dict[str, Any]:
    _ensure_data_dir()
    if not _DATA_FILE.exists():
        _write_data(_SEED)
        return _SEED
    try:
        return json.loads(_DATA_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise HTTPException(
            status_code=500, detail=f"Failed to read data store: {exc}"
        ) from exc


def _write_data(payload: Dict[str, Any]) -> None:
    _ensure_data_dir()
    tmp = _DATA_FILE.with_suffix(".tmp")
    try:
        tmp.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        tmp.replace(_DATA_FILE)
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


class VolumeStatusUpdate(BaseModel):
    status: str  # todo | in_progress | done


class LoginRequest(BaseModel):
    username: str
    password: str


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
        payload["volumes"] = current.get("volumes", _SEED["volumes"])
    _write_data(payload)
    return {"ok": True}


@router.post("/data/reset")
def reset_pm_data():
    """Revert the data file to original seed and return state (without volumes)."""
    _write_data(_SEED)
    result = {k: v for k, v in _SEED.items() if k != "volumes"}
    result["global_progress"] = _compute_global_progress(_SEED["volumes"])
    return result


# ── Volume endpoints ──────────────────────────────────────────────────────────


@router.get("/volumes")
def get_volumes(
    assignee: Optional[str] = Query(None, description="Filter by worker key"),
    status: Optional[str] = Query(
        None, description="Filter by status: todo|in_progress|done"
    ),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    """Return paginated volume list with optional assignee/status filters."""
    data = _read_data()
    volumes: List[Dict[str, Any]] = data.get("volumes", [])

    # Apply filters
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
async def update_volume_status(volume_id: str, body: VolumeStatusUpdate):
    """Update a single volume's status atomically."""
    valid_statuses = {"todo", "in_progress", "done"}
    if body.status not in valid_statuses:
        raise HTTPException(
            status_code=400, detail=f"status must be one of {valid_statuses}"
        )

    data = _read_data()
    volumes: List[Dict[str, Any]] = data.get("volumes", [])

    for vol in volumes:
        if vol["id"] == volume_id:
            vol["status"] = body.status
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
