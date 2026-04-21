from typing import Any, Dict, List, Sequence

from server_api.project_manager.discovery import (
    PROJECT_MANAGER_SUPPORTED_VOLUME_INPUTS,
)

PROJECT_MANAGER_WORKERS: List[Dict[str, Any]] = [
    {"key": "alex", "name": "Alex Rivera", "avatarColor": "#1890ff"},
    {"key": "jordan", "name": "Jordan Smith", "avatarColor": "#52c41a"},
    {"key": "taylor", "name": "Sam Taylor", "avatarColor": "#fadb14"},
    {"key": "morgan", "name": "Morgan Lee", "avatarColor": "#eb2f96"},
]

VALID_VOLUME_STATUSES = ["todo", "in_progress", "done"]


def build_default_users(
    workers: Sequence[Dict[str, Any]] | None = None,
) -> List[Dict[str, Any]]:
    worker_rows = [dict(worker) for worker in (workers or PROJECT_MANAGER_WORKERS)]
    users = [
        {
            "username": "admin",
            "password": "admin123",
            "name": "Project Manager",
            "role": "admin",
            "key": "admin",
        }
    ]
    for worker in worker_rows:
        users.append(
            {
                "username": worker["key"],
                "password": f'{worker["key"]}123',
                "name": worker["name"],
                "role": "worker",
                "key": worker["key"],
            }
        )
    return users


def build_empty_state(
    *,
    project_name: str = "New Project",
    description: str = "No storage synced yet.",
    workers: Sequence[Dict[str, Any]] | None = None,
    users: Sequence[Dict[str, Any]] | None = None,
) -> Dict[str, Any]:
    worker_rows = [dict(worker) for worker in (workers or PROJECT_MANAGER_WORKERS)]
    user_rows = [dict(user) for user in (users or build_default_users(worker_rows))]
    quota_rows = []
    proofreader_rows = []

    for index, worker in enumerate(worker_rows, start=1):
        quota_rows.append(
            {
                "key": str(index),
                "name": worker["name"],
                "worker_key": worker["key"],
                "datasets": [],
                "mon": 0,
                "tue": 0,
                "wed": 0,
                "thu": 0,
                "fri": 0,
                "sat": 0,
                "sun": 0,
                "actualMon": 0,
                "actualTue": 0,
                "actualWed": 0,
                "actualThu": 0,
                "actualFri": 0,
                "actualSat": 0,
                "actualSun": 0,
            }
        )
        proofreader_rows.append(
            {
                "key": str(index),
                "name": worker["name"],
                "worker_key": worker["key"],
                "avatarColor": worker["avatarColor"],
                "role": "Proofreader",
                "totalPoints": 0,
                "weeklyPoints": 0,
                "weeklyQuota": 0,
                "accuracy": 0,
                "lastActive": "Never",
                "status": "offline",
            }
        )

    return {
        "project_info": {
            "name": project_name,
            "description": description,
            "version": "0.1.0",
        },
        "volumes": [],
        "quota_data": quota_rows,
        "proofreader_data": proofreader_rows,
        "throughput_data": [],
        "datasets": [],
        "milestones": [],
        "cumulative_data": [0],
        "cumulative_target": [0],
        "at_risk": [],
        "upcoming_milestones": [],
        "msg_preview": "",
        "workers": worker_rows,
        "users": user_rows,
    }


def build_schema_reference() -> Dict[str, Any]:
    return {
        "top_level_fields": [
            {
                "field": "project_info",
                "level": "required",
                "type": "object",
                "description": "Project name and description shown in the Project Manager header.",
            },
            {
                "field": "workers",
                "level": "required",
                "type": "array",
                "description": "Worker directory used for assignee dropdowns and worker dashboards.",
            },
            {
                "field": "users",
                "level": "required",
                "type": "array",
                "description": "Login credentials for admin and worker views.",
            },
            {
                "field": "volumes",
                "level": "required",
                "type": "array",
                "description": "Trackable units of work. Each row becomes one item in Volume Tracker.",
            },
            {
                "field": "quota_data",
                "level": "recommended",
                "type": "array",
                "description": "Weekly planning rows per worker. Needed for a useful quota screen.",
            },
            {
                "field": "proofreader_data",
                "level": "recommended",
                "type": "array",
                "description": "Worker profile cards for progress screens.",
            },
            {
                "field": "msg_preview",
                "level": "recommended",
                "type": "string",
                "description": "Editable draft text used by the quota communication panel.",
            },
            {
                "field": "datasets",
                "level": "optional",
                "type": "array",
                "description": "Dataset rollups for the dashboard. Leave empty if you do not have them yet.",
            },
            {
                "field": "throughput_data",
                "level": "optional",
                "type": "array",
                "description": "Demo or computed throughput chart data.",
            },
            {
                "field": "milestones",
                "level": "optional",
                "type": "array",
                "description": "Timeline markers for planning dashboards.",
            },
            {
                "field": "cumulative_data",
                "level": "optional",
                "type": "array",
                "description": "Historical cumulative progress points.",
            },
            {
                "field": "cumulative_target",
                "level": "optional",
                "type": "array",
                "description": "Historical target curve for the cumulative chart.",
            },
            {
                "field": "at_risk",
                "level": "optional",
                "type": "array",
                "description": "Dashboard warnings and labels.",
            },
            {
                "field": "upcoming_milestones",
                "level": "optional",
                "type": "array",
                "description": "Small milestone cards used on the dashboard.",
            },
        ],
        "volume_fields": [
            {
                "field": "id",
                "level": "required",
                "type": "string",
                "description": "Stable unique ID for the volume. Using the relative file path works best.",
            },
            {
                "field": "filename",
                "level": "required",
                "type": "string",
                "description": "Display name shown in tables.",
            },
            {
                "field": "rel_path",
                "level": "required",
                "type": "string",
                "description": "Path relative to the storage root. The ingestion script preserves state by this field.",
            },
            {
                "field": "assignee",
                "level": "required",
                "type": "string|null",
                "description": "Worker key from the workers array, or null for unassigned.",
            },
            {
                "field": "status",
                "level": "required",
                "type": "string",
                "description": "One of todo, in_progress, or done.",
            },
        ],
        "worker_fields": [
            {
                "field": "key",
                "level": "required",
                "type": "string",
                "description": "Stable worker identifier used across users, quotas, and volumes.",
            },
            {
                "field": "name",
                "level": "required",
                "type": "string",
                "description": "Display label shown in the UI.",
            },
            {
                "field": "avatarColor",
                "level": "recommended",
                "type": "string",
                "description": "Hex color used in worker profile cards.",
            },
        ],
        "user_fields": [
            {
                "field": "username",
                "level": "required",
                "type": "string",
                "description": "Login username.",
            },
            {
                "field": "password",
                "level": "required",
                "type": "string",
                "description": "Login password stored in plain JSON by this prototype backend.",
            },
            {
                "field": "name",
                "level": "required",
                "type": "string",
                "description": "Display name shown after login.",
            },
            {
                "field": "role",
                "level": "required",
                "type": "string",
                "description": "Either admin or worker.",
            },
            {
                "field": "key",
                "level": "required",
                "type": "string",
                "description": "Role key. Worker keys should match the workers array.",
            },
        ],
        "valid_statuses": list(VALID_VOLUME_STATUSES),
        "notes": [
            "The smallest useful JSON has project_info, workers, users, and volumes.",
            "If you plan to use the quota and progress screens, include quota_data and proofreader_data too.",
            "The Project Manager does not require analytics sections like datasets or milestones to be present on day one.",
            "Storage ingestion scans the configured root for supported volume files, dataset containers, and image-stack directories, then replaces the volumes array while preserving status and assignee by rel_path.",
        ],
        "supported_volume_inputs": list(PROJECT_MANAGER_SUPPORTED_VOLUME_INPUTS),
        "blank_template": build_empty_state(
            project_name="My EM Project",
            description="Volumes and planning data for an annotation project.",
        ),
        "example_volume": {
            "id": "hippocampus/vol_001_em.tif",
            "filename": "vol_001_em.tif",
            "rel_path": "hippocampus/vol_001_em.tif",
            "assignee": None,
            "status": "todo",
        },
    }
