"""Shared API error responses and exception handlers."""

import logging
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from server_api.chatbot.logging_utils import request_id_from_request


logger = logging.getLogger(__name__)
ERROR_SCHEMA_VERSION = 1


def _message_from_detail(detail: Any, fallback: str) -> str:
    if isinstance(detail, str) and detail.strip():
        return detail.strip()
    if isinstance(detail, dict):
        for key in ("user_message", "message", "detail", "reason"):
            value = detail.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return fallback


def _error_metadata(status_code: int) -> Dict[str, Any]:
    if status_code == 400:
        return {
            "code": "invalid_request",
            "category": "validation",
            "title": "Request could not be completed",
            "retryable": False,
            "recovery_actions": ["review_input"],
        }
    if status_code == 401:
        return {
            "code": "authentication_required",
            "category": "authentication",
            "title": "Authentication required",
            "retryable": False,
            "recovery_actions": ["sign_in"],
        }
    if status_code == 403:
        return {
            "code": "permission_denied",
            "category": "authorization",
            "title": "Permission denied",
            "retryable": False,
            "recovery_actions": ["contact_admin"],
        }
    if status_code == 404:
        return {
            "code": "not_found",
            "category": "resource",
            "title": "Resource not found",
            "retryable": False,
            "recovery_actions": ["go_back"],
        }
    if status_code == 409:
        return {
            "code": "conflict",
            "category": "state",
            "title": "State conflict",
            "retryable": False,
            "recovery_actions": ["refresh"],
        }
    if status_code == 413:
        return {
            "code": "payload_too_large",
            "category": "resource",
            "title": "Request is too large",
            "retryable": False,
            "recovery_actions": ["reduce_request"],
        }
    if status_code == 422:
        return {
            "code": "validation_failed",
            "category": "validation",
            "title": "Some request values are invalid",
            "retryable": False,
            "recovery_actions": ["review_input"],
        }
    if status_code == 429:
        return {
            "code": "rate_limited",
            "category": "availability",
            "title": "Too many requests",
            "retryable": True,
            "recovery_actions": ["retry_later"],
        }
    if status_code in {502, 503, 504}:
        return {
            "code": "service_unavailable",
            "category": "availability",
            "title": "Service temporarily unavailable",
            "retryable": True,
            "recovery_actions": ["retry"],
        }
    if status_code >= 500:
        return {
            "code": "internal_error",
            "category": "internal",
            "title": "Unexpected server error",
            "retryable": True,
            "recovery_actions": ["retry", "view_logs"],
        }
    return {
        "code": "request_failed",
        "category": "request",
        "title": "Request failed",
        "retryable": False,
        "recovery_actions": ["go_back"],
    }


def build_error_response(
    *,
    status_code: int,
    request_id: str,
    detail: Any,
    message_fallback: str,
    headers: Optional[Dict[str, str]] = None,
    validation_errors: Optional[List[Dict[str, Any]]] = None,
) -> JSONResponse:
    metadata = _error_metadata(status_code)
    error = {
        "schema_version": ERROR_SCHEMA_VERSION,
        **metadata,
        "message": _message_from_detail(detail, message_fallback),
        "request_id": request_id,
    }
    if validation_errors is not None:
        error["validation_errors"] = validation_errors

    response_headers = dict(headers or {})
    response_headers.setdefault("x-request-id", request_id)
    response_headers.setdefault("cache-control", "no-store")
    return JSONResponse(
        status_code=status_code,
        content=jsonable_encoder({"detail": detail, "error": error}),
        headers=response_headers,
    )


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(
        request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        request_id = request_id_from_request(request)
        return build_error_response(
            status_code=exc.status_code,
            request_id=request_id,
            detail=exc.detail,
            message_fallback="The request could not be completed.",
            headers=exc.headers,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        request_id = request_id_from_request(request)
        errors = exc.errors()
        return build_error_response(
            status_code=422,
            request_id=request_id,
            detail=errors,
            message_fallback="Review the highlighted request values and try again.",
            validation_errors=errors,
        )

    @app.exception_handler(Exception)
    async def unexpected_exception_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        request_id = request_id_from_request(request)
        logger.exception(
            "Unhandled API error request_id=%s method=%s path=%s",
            request_id,
            request.method,
            request.url.path,
            exc_info=exc,
        )
        return build_error_response(
            status_code=500,
            request_id=request_id,
            detail="An unexpected server error occurred.",
            message_fallback="An unexpected server error occurred.",
        )
