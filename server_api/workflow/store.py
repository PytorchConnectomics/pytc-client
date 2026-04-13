from __future__ import annotations

from collections import defaultdict
from typing import DefaultDict, List

from .models import WorkflowEvent

_workflow_events: DefaultDict[str, List[WorkflowEvent]] = defaultdict(list)


def get_events(workflow_id: str) -> list[WorkflowEvent]:
    return list(_workflow_events.get(str(workflow_id), []))


def set_events(workflow_id: str, events: list[WorkflowEvent]) -> None:
    _workflow_events[str(workflow_id)] = list(events)


def clear_events() -> None:
    _workflow_events.clear()
