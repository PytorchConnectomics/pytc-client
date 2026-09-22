import logging
import re
import time
import uuid
from typing import Any, Optional

logger = logging.getLogger(__name__)
_REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")


def request_id_from_request(request: Any) -> str:
    existing = getattr(getattr(request, "state", None), "request_id", None)
    if existing:
        return existing
    supplied_request_id = request.headers.get("x-request-id")
    request_id = (
        supplied_request_id
        if supplied_request_id and _REQUEST_ID_PATTERN.fullmatch(supplied_request_id)
        else str(uuid.uuid4())
    )
    if getattr(request, "state", None) is not None:
        request.state.request_id = request_id
    return request_id


def log_request_summary(
    *,
    request_id: str,
    endpoint: str,
    start_time: float,
    status: str,
    error_type: Optional[str] = None,
) -> None:
    latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
    logger.info(
        "request_summary request_id=%s endpoint=%s latency_ms=%s status=%s error_type=%s",
        request_id,
        endpoint,
        latency_ms,
        status,
        error_type or "none",
    )
