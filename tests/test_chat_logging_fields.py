import logging
import time

from server_api.chatbot import logging_utils


def test_standardized_summary_log_success_fields(caplog):
    caplog.set_level(logging.INFO)

    logging_utils.log_request_summary(
        request_id="req-123",
        endpoint="/chat/query",
        start_time=time.perf_counter() - 0.01,
        status="ok",
    )

    message = caplog.records[-1].getMessage()
    assert "request_id=req-123" in message
    assert "endpoint=/chat/query" in message
    assert "latency_ms=" in message
    assert "status=ok" in message
    assert "error_type=none" in message


def test_standardized_summary_log_error_fields_and_no_payload_leak(caplog):
    caplog.set_level(logging.INFO)
    sensitive_query = "my secret token is abc123"

    logging_utils.log_request_summary(
        request_id="req-456",
        endpoint="/chat/helper/query",
        start_time=time.perf_counter() - 0.02,
        status="error",
        error_type="HTTPException",
    )

    message = caplog.records[-1].getMessage()
    assert "request_id=req-456" in message
    assert "endpoint=/chat/helper/query" in message
    assert "latency_ms=" in message
    assert "status=error" in message
    assert "error_type=HTTPException" in message
    assert sensitive_query not in message
