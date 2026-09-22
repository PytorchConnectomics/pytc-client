import hashlib
import json
import pathlib
import subprocess
import sys
import time

import pytest

dbos = pytest.importorskip("dbos")
from dbos import DBOSClient

RESULT_PREFIX = "DBOS_SPIKE_RESULT="
RUNNER_MODULE = "spikes.dbos_operation.runner"
PROGRESS_EVENT = "operation_progress"


def _command(*args):
    return [sys.executable, "-m", RUNNER_MODULE, *map(str, args)]


def _parse_result(output):
    for line in reversed(output.splitlines()):
        if line.startswith(RESULT_PREFIX):
            return json.loads(line[len(RESULT_PREFIX) :])
    raise AssertionError(f"Spike runner did not emit a result: {output[-2000:]}")


def _run(*args, timeout=30):
    completed = subprocess.run(
        _command(*args),
        check=True,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    return _parse_result(completed.stdout)


def _database_url(path):
    return f"sqlite:///{path.resolve()}"


def _client_state(database, workflow_id):
    client = DBOSClient(system_database_url=_database_url(database))
    try:
        rows = client.list_workflows(workflow_ids=[workflow_id], limit=1)
        status = rows[0].status if rows else None
        progress = client.get_event(
            workflow_id,
            PROGRESS_EVENT,
            timeout_seconds=0,
        )
        return status, progress
    finally:
        client.destroy()


def _wait_for(database, workflow_id, predicate, timeout=15):
    deadline = time.monotonic() + timeout
    last_state = (None, None)
    while time.monotonic() < deadline:
        try:
            last_state = _client_state(database, workflow_id)
        except Exception:
            time.sleep(0.05)
            continue
        if predicate(*last_state):
            return last_state
        time.sleep(0.05)
    raise AssertionError(f"Timed out waiting for DBOS state; last state={last_state}")


def _markers(workspace, workflow_id):
    storage_key = hashlib.sha256(workflow_id.encode("utf-8")).hexdigest()[:20]
    return workspace / "markers" / storage_key


def test_idempotent_submission_executes_external_effects_once(tmp_path):
    database = tmp_path / "dbos.sqlite"
    workspace = tmp_path / "workspace"
    workflow_id = "operation-idempotency-1"

    result = _run(
        "execute",
        "--database",
        database,
        "--workspace",
        workspace,
        "--workflow-id",
        workflow_id,
        "--correlation-id",
        "request-idempotency-1",
        "--steps",
        3,
        "--duplicate-submission",
    )

    assert result["workflow_id"] == workflow_id
    assert result["duplicate_workflow_id"] == workflow_id
    assert result["workflow"]["status"] == "SUCCESS"
    assert result["progress"]["progress"] == 1.0
    marker_dir = _markers(workspace, workflow_id)
    assert len(list(marker_dir.glob("step-*.json"))) == 3
    assert not (marker_dir / "duplicate-attempts.jsonl").exists()


def test_queued_cancellation_prevents_execution(tmp_path):
    database = tmp_path / "dbos.sqlite"
    workspace = tmp_path / "workspace"
    workflow_id = "operation-cancel-queued"

    submitted = _run(
        "execute",
        "--database",
        database,
        "--workspace",
        workspace,
        "--workflow-id",
        workflow_id,
        "--steps",
        3,
        "--no-register-queue",
        "--no-wait",
    )
    assert submitted["workflow"]["status"] == "ENQUEUED"

    cancelled = _run(
        "cancel",
        "--database",
        database,
        "--workflow-id",
        workflow_id,
    )
    assert cancelled["workflow"]["status"] == "CANCELLED"
    assert not _markers(workspace, workflow_id).exists()


def test_running_cancellation_stops_at_durable_boundary(tmp_path):
    database = tmp_path / "dbos.sqlite"
    workspace = tmp_path / "workspace"
    workflow_id = "operation-cancel-running"
    process = subprocess.Popen(
        _command(
            "execute",
            "--database",
            database,
            "--workspace",
            workspace,
            "--workflow-id",
            workflow_id,
            "--steps",
            20,
            "--step-runtime",
            0.01,
            "--inter-step-delay",
            0.5,
        ),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    try:
        _wait_for(
            database,
            workflow_id,
            lambda status, progress: (
                status == "PENDING"
                and isinstance(progress, dict)
                and progress.get("completed_steps", 0) >= 1
            ),
        )
        client = DBOSClient(system_database_url=_database_url(database))
        try:
            client.cancel_workflow(workflow_id)
        finally:
            client.destroy()
        _wait_for(
            database,
            workflow_id,
            lambda status, _progress: status == "CANCELLED",
        )
        output, _ = process.communicate(timeout=15)
        result = _parse_result(output)
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=5)

    assert result["cancelled"] is True
    marker_dir = _markers(workspace, workflow_id)
    completed_markers = list(marker_dir.glob("step-*.json"))
    assert 1 <= len(completed_markers) < 20
    assert not (marker_dir / "duplicate-attempts.jsonl").exists()


def test_process_kill_recovers_from_last_completed_step(tmp_path):
    database = tmp_path / "dbos.sqlite"
    workspace = tmp_path / "workspace"
    workflow_id = "operation-restart-recovery"
    process = subprocess.Popen(
        _command(
            "execute",
            "--database",
            database,
            "--workspace",
            workspace,
            "--workflow-id",
            workflow_id,
            "--correlation-id",
            "request-recovery-1",
            "--steps",
            3,
            "--step-runtime",
            0.01,
            "--inter-step-delay",
            3,
        ),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        status_before, progress_before = _wait_for(
            database,
            workflow_id,
            lambda status, progress: (
                status == "PENDING"
                and isinstance(progress, dict)
                and progress.get("completed_steps") == 1
            ),
        )
        assert status_before == "PENDING"
        assert progress_before["correlation_id"] == "request-recovery-1"
        process.kill()
        process.wait(timeout=5)
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=5)

    status_after_kill, persisted_progress = _wait_for(
        database,
        workflow_id,
        lambda status, progress: (
            status == "PENDING"
            and isinstance(progress, dict)
            and progress.get("completed_steps") == 1
        ),
    )
    assert status_after_kill == "PENDING"
    assert persisted_progress["progress"] == pytest.approx(1 / 3)

    recovered = _run(
        "recover",
        "--database",
        database,
        "--workflow-id",
        workflow_id,
        timeout=20,
    )
    assert recovered["workflow"]["status"] == "SUCCESS"
    assert recovered["workflow"]["recovery_attempts"] >= 2
    assert recovered["progress"]["completed_steps"] == 3
    assert recovered["progress"]["correlation_id"] == "request-recovery-1"

    marker_dir = _markers(workspace, workflow_id)
    assert len(list(marker_dir.glob("step-*.json"))) == 3
    assert not (marker_dir / "duplicate-attempts.jsonl").exists()
