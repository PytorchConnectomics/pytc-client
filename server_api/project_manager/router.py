"""
Project Manager — FastAPI router
Provides two endpoints that read/write a local JSON file as the single source
of truth for Project Manager state (quota data, proofreader data, etc.).
"""
from __future__ import annotations

import json
import pathlib
from typing import Any, Dict

from fastapi import APIRouter, HTTPException, Request

router = APIRouter()

# ── Paths ─────────────────────────────────────────────────────────────────────

# data_store/ lives alongside server_api/ at the project root level
_HERE      = pathlib.Path(__file__).resolve().parent          # server_api/project_manager/
_API_DIR   = _HERE.parent                                     # server_api/
_DATA_DIR  = _API_DIR / "data_store"
_DATA_FILE = _DATA_DIR / "project_manager_data.json"

# ── Seed Data (mirrors the React front-end seed constants) ────────────────────

_SEED: Dict[str, Any] = {
    "quota_data": [
        {
            "key": "1",
            "name": "Alex Rivera",
            "datasets": ["Hippocampus_CA3", "Motor_Cortex_M1"],
            "mon": 300, "tue": 300, "wed": 300, "thu": 300, "fri": 300, "sat": 150, "sun": 100,
            "actualMon": 310, "actualTue": 290, "actualWed": 320,
            "actualThu": 280, "actualFri": 300, "actualSat": 160, "actualSun": 90,
        },
        {
            "key": "2",
            "name": "Jordan Smith",
            "datasets": ["Cerebellum_PC"],
            "mon": 250, "tue": 250, "wed": 250, "thu": 250, "fri": 250, "sat": 0, "sun": 0,
            "actualMon": 240, "actualTue": 260, "actualWed": 230,
            "actualThu": 250, "actualFri": 220, "actualSat": 0, "actualSun": 0,
        },
        {
            "key": "3",
            "name": "Sam Taylor",
            "datasets": ["Retina_GCL"],
            "mon": 200, "tue": 200, "wed": 200, "thu": 200, "fri": 200, "sat": 250, "sun": 250,
            "actualMon": 180, "actualTue": 190, "actualWed": 170,
            "actualThu": 210, "actualFri": 200, "actualSat": 100, "actualSun": 0,
        },
        {
            "key": "4",
            "name": "Casey Chen",
            "datasets": ["Visual_Cortex_V1"],
            "mon": 240, "tue": 240, "wed": 240, "thu": 240, "fri": 240, "sat": 0, "sun": 0,
            "actualMon": 250, "actualTue": 260, "actualWed": 270,
            "actualThu": 240, "actualFri": 230, "actualSat": 0, "actualSun": 0,
        },
    ],
    "proofreader_data": [
        {
            "key": "1", "name": "Alex Rivera", "avatarColor": "#1890ff",
            "role": "Senior Annotator", "totalPoints": 12450,
            "weeklyPoints": 1420, "weeklyQuota": 1750, "accuracy": 98.5,
            "lastActive": "2 mins ago", "status": "online",
        },
        {
            "key": "2", "name": "Jordan Smith", "avatarColor": "#52c41a",
            "role": "Proofreader", "totalPoints": 8900,
            "weeklyPoints": 1100, "weeklyQuota": 1500, "accuracy": 94.2,
            "lastActive": "15 mins ago", "status": "online",
        },
        {
            "key": "3", "name": "Sam Taylor", "avatarColor": "#fadb14",
            "role": "Proofreader", "totalPoints": 5600,
            "weeklyPoints": 850, "weeklyQuota": 1500, "accuracy": 92.1,
            "lastActive": "1 hour ago", "status": "away",
        },
        {
            "key": "4", "name": "Casey Chen", "avatarColor": "#eb2f96",
            "role": "Junior Annotator", "totalPoints": 3200,
            "weeklyPoints": 1250, "weeklyQuota": 1200, "accuracy": 96.8,
            "lastActive": "3 hours ago", "status": "offline",
        },
        {
            "key": "5", "name": "Robin Banks", "avatarColor": "#722ed1",
            "role": "Proofreader", "totalPoints": 7100,
            "weeklyPoints": 300, "weeklyQuota": 1500, "accuracy": 89.5,
            "lastActive": "Yesterday", "status": "offline",
        },
    ],
    "throughput_data": [
        {"day": "Mon", "count": 4200},
        {"day": "Tue", "count": 3800},
        {"day": "Wed", "count": 5100},
        {"day": "Thu", "count": 4700},
        {"day": "Fri", "count": 5300},
        {"day": "Sat", "count": 1200},
        {"day": "Sun", "count": 900},
    ],
    "datasets": [
        {"key": "1", "name": "Hippocampus_CA3", "experiment": "Synapse detection", "total": 12450, "proofread": 38, "status": "in_progress", "eta": "Jan 18", "priority": "high"},
        {"key": "2", "name": "Motor_Cortex_M1", "experiment": "Axon tracing", "total": 9800, "proofread": 72, "status": "in_progress", "eta": "Jan 22", "priority": "high"},
        {"key": "3", "name": "Cerebellum_PC", "experiment": "Dendrite segmentation", "total": 6200, "proofread": 91, "status": "done", "eta": "Complete", "priority": "normal"},
        {"key": "4", "name": "Retina_GCL", "experiment": "Cell classification", "total": 3300, "proofread": 5, "status": "blocked", "eta": "TBD", "priority": "high"},
        {"key": "5", "name": "Olfactory_Bulb", "experiment": "Glomeruli mapping", "total": 7650, "proofread": 0, "status": "not_started", "eta": "Feb 28", "priority": "normal"},
        {"key": "6", "name": "Visual_Cortex_V1", "experiment": "Spine detection", "total": 15000, "proofread": 55, "status": "in_progress", "eta": "Feb 10", "priority": "normal"},
    ],
    "milestones": [
        { "label": "Model v1", "date": "2025-11-15", "color": "#1890ff" },
        { "label": "Mid-Review", "date": "2025-12-20", "color": "#722ed1" },
        { "label": "Model v2", "date": "2026-01-28", "color": "#1890ff" },
        { "label": "Data Freeze", "date": "2026-02-15", "color": "#fa8c16" },
        { "label": "Model v3", "date": "2026-03-20", "color": "#1890ff" },
    ],
    "cumulative_data": [0, 480, 1100, 1950, 2800, 3900, 5100, 6200, 7450, 8600, 9900, 11200, 12600, 13900, 15400, 17000, 18500, 20100, 21800, 23400, 25000, 26700, 28500, 30200, 32000, 33800],
    "cumulative_target": [0, 600, 1200, 1800, 2400, 3000, 3600, 4800, 6000, 7200, 8400, 9600, 10800, 12000, 13200, 14400, 15600, 16800, 18000, 19200, 20400, 21600, 22800, 24000, 25200, 26400],
    "at_risk": [
        { "label": "Hippocampus_CA3", "reason": "Low progress (38%)", "icon": "progress" },
        { "label": "Motor_Cortex_M1", "reason": "Deadline approaching", "icon": "clock" },
        { "label": "Retina_GCL", "reason": "Blocked — awaiting data", "icon": "blocked" },
    ],
    "upcoming_milestones": [
        { "label": "Model v2 data freeze", "date": "JAN 28" },
        { "label": "Mid-project review", "date": "FEB 5" },
        { "label": "Final data freeze", "date": "FEB 15" },
        { "label": "Model v3 launch", "date": "MAR 20" },
    ],
    "msg_preview": (
        "Hi Team,\n\nI've just assigned the quotas for the upcoming week. "
        "Please review your targets in the dashboard. Our goal for this week "
        "is to maintain 95%+ accuracy while meeting the sample volume targets.\n\nGood luck!"
    ),
}

# ── Helpers ───────────────────────────────────────────────────────────────────

def _ensure_data_dir() -> None:
    _DATA_DIR.mkdir(parents=True, exist_ok=True)


def _read_data() -> Dict[str, Any]:
    """Return current PM state, initialising from seed if the file is missing."""
    _ensure_data_dir()
    if not _DATA_FILE.exists():
        _write_data(_SEED)
        return _SEED
    try:
        return json.loads(_DATA_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise HTTPException(status_code=500, detail=f"Failed to read data store: {exc}") from exc


def _write_data(payload: Dict[str, Any]) -> None:
    """Atomically overwrite the data file."""
    _ensure_data_dir()
    # Write to a temp file alongside the target, then rename for atomicity
    tmp = _DATA_FILE.with_suffix(".tmp")
    try:
        tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(_DATA_FILE)
    except OSError as exc:
        raise HTTPException(status_code=500, detail=f"Failed to write data store: {exc}") from exc


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/data")
def get_pm_data():
    """Return the full Project Manager state from disk."""
    return _read_data()


@router.post("/data")
async def save_pm_data(req: Request):
    """Overwrite the Project Manager state with the supplied payload."""
    try:
        payload = await req.json()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid JSON body: {exc}") from exc
    _write_data(payload)
    return {"ok": True}


@router.post("/data/reset")
def reset_pm_data():
    """Overwrite the data file with the original seed data and return it."""
    _write_data(_SEED)
    return _SEED
