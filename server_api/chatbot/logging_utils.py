import logging
import time
import uuid
from typing import Any, Optional

logger = logging.getLogger(__name__)


def request_id_from_request(request: Any) -> str:
    return request.headers.get("x-request-id") or str(uuid.uuid4())


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
