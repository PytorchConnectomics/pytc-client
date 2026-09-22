from __future__ import annotations

import argparse
import json
import pathlib
from typing import Any, Dict, Optional, Sequence

from dbos import DBOS, DBOSClient, SetWorkflowID

from .runtime import (
    APP_NAME,
    APP_VERSION,
    PROGRESS_EVENT,
    QUEUE_NAME,
    synthetic_operation,
)

RESULT_PREFIX = "DBOS_SPIKE_RESULT="


def sqlite_database_url(database_path: str) -> str:
    path = pathlib.Path(database_path).expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{path}"


def _workflow_status(database_url: str, workflow_id: str) -> Optional[Dict[str, Any]]:
    client = DBOSClient(system_database_url=database_url)
    try:
        rows = client.list_workflows(workflow_ids=[workflow_id], limit=1)
        if not rows:
            return None
        row = rows[0]
        return {
            "workflow_id": row.workflow_id,
            "status": row.status,
            "name": row.name,
            "queue_name": row.queue_name,
            "executor_id": row.executor_id,
            "app_version": row.app_version,
            "recovery_attempts": row.recovery_attempts,
            "output": row.output,
            "error": str(row.error) if row.error else None,
        }
    finally:
        client.destroy()


def _progress(database_url: str, workflow_id: str) -> Optional[Dict[str, Any]]:
    client = DBOSClient(system_database_url=database_url)
    try:
        value = client.get_event(workflow_id, PROGRESS_EVENT, timeout_seconds=0)
        return value if isinstance(value, dict) else None
    finally:
        client.destroy()


def _launch(database_url: str, *, register_queue: bool) -> None:
    DBOS(
        config={
            "name": APP_NAME,
            "application_version": APP_VERSION,
            # A single-server replacement process must reuse the executor identity
            # so startup recovery can claim that executor's interrupted workflows.
            "executor_id": "pytc-dbos-operation-spike",
            "system_database_url": database_url,
        }
    )
    DBOS.launch()
    if register_queue:
        DBOS.register_queue(
            QUEUE_NAME,
            concurrency=1,
            worker_concurrency=1,
            polling_interval_sec=0.05,
        )


def _wait_for_result(handle: Any, database_url: str) -> Dict[str, Any]:
    try:
        result = handle.get_result()
        return {"result": result, "cancelled": False}
    except Exception:
        status = _workflow_status(database_url, handle.workflow_id)
        if status and status["status"] == "CANCELLED":
            return {"result": None, "cancelled": True}
        raise


def execute(args: argparse.Namespace) -> Dict[str, Any]:
    database_url = sqlite_database_url(args.database)
    pathlib.Path(args.workspace).expanduser().resolve().mkdir(
        parents=True, exist_ok=True
    )
    _launch(database_url, register_queue=args.register_queue)
    queue_name = QUEUE_NAME if args.register_queue else f"{QUEUE_NAME}-paused"
    try:
        with SetWorkflowID(args.workflow_id):
            first = DBOS.enqueue_workflow(
                queue_name,
                synthetic_operation,
                str(pathlib.Path(args.workspace).expanduser().resolve()),
                args.workflow_id,
                args.correlation_id,
                args.steps,
                args.step_runtime,
                args.inter_step_delay,
            )
        duplicate_workflow_id = None
        if args.duplicate_submission:
            with SetWorkflowID(args.workflow_id):
                duplicate = DBOS.enqueue_workflow(
                    queue_name,
                    synthetic_operation,
                    str(pathlib.Path(args.workspace).expanduser().resolve()),
                    args.workflow_id,
                    args.correlation_id,
                    args.steps,
                    args.step_runtime,
                    args.inter_step_delay,
                )
            duplicate_workflow_id = duplicate.workflow_id

        wait_result = (
            _wait_for_result(first, database_url) if args.wait else {"result": None}
        )
        return {
            "workflow_id": first.workflow_id,
            "duplicate_workflow_id": duplicate_workflow_id,
            "database_url": database_url,
            "progress": _progress(database_url, args.workflow_id),
            "workflow": _workflow_status(database_url, args.workflow_id),
            **wait_result,
        }
    finally:
        DBOS.destroy(workflow_completion_timeout_sec=1)


def recover(args: argparse.Namespace) -> Dict[str, Any]:
    database_url = sqlite_database_url(args.database)
    _launch(database_url, register_queue=True)
    try:
        handle = DBOS.retrieve_workflow(args.workflow_id)
        wait_result = _wait_for_result(handle, database_url)
        return {
            "workflow_id": handle.workflow_id,
            "database_url": database_url,
            "progress": _progress(database_url, args.workflow_id),
            "workflow": _workflow_status(database_url, args.workflow_id),
            **wait_result,
        }
    finally:
        DBOS.destroy(workflow_completion_timeout_sec=1)


def status(args: argparse.Namespace) -> Dict[str, Any]:
    database_url = sqlite_database_url(args.database)
    return {
        "workflow_id": args.workflow_id,
        "database_url": database_url,
        "progress": _progress(database_url, args.workflow_id),
        "workflow": _workflow_status(database_url, args.workflow_id),
    }


def cancel(args: argparse.Namespace) -> Dict[str, Any]:
    database_url = sqlite_database_url(args.database)
    client = DBOSClient(system_database_url=database_url)
    try:
        client.cancel_workflow(args.workflow_id)
    finally:
        client.destroy()
    return status(args)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the isolated DBOS durable-operation spike."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    execute_parser = subparsers.add_parser(
        "execute", help="Idempotently enqueue a synthetic operation."
    )
    execute_parser.add_argument("--database", required=True)
    execute_parser.add_argument("--workspace", required=True)
    execute_parser.add_argument("--workflow-id", required=True)
    execute_parser.add_argument("--correlation-id", default="dbos-spike")
    execute_parser.add_argument("--steps", type=int, default=3)
    execute_parser.add_argument("--step-runtime", type=float, default=0.01)
    execute_parser.add_argument("--inter-step-delay", type=float, default=0.05)
    execute_parser.add_argument(
        "--register-queue", action=argparse.BooleanOptionalAction, default=True
    )
    execute_parser.add_argument(
        "--duplicate-submission", action="store_true", default=False
    )
    execute_parser.add_argument(
        "--wait", action=argparse.BooleanOptionalAction, default=True
    )
    execute_parser.set_defaults(handler=execute)

    recover_parser = subparsers.add_parser(
        "recover", help="Launch a new executor and wait for recovered work."
    )
    recover_parser.add_argument("--database", required=True)
    recover_parser.add_argument("--workflow-id", required=True)
    recover_parser.set_defaults(handler=recover)

    status_parser = subparsers.add_parser(
        "status", help="Read durable status and progress without launching a worker."
    )
    status_parser.add_argument("--database", required=True)
    status_parser.add_argument("--workflow-id", required=True)
    status_parser.set_defaults(handler=status)

    cancel_parser = subparsers.add_parser(
        "cancel", help="Cancel queued or running work through DBOSClient."
    )
    cancel_parser.add_argument("--database", required=True)
    cancel_parser.add_argument("--workflow-id", required=True)
    cancel_parser.set_defaults(handler=cancel)
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    result = args.handler(args)
    print(RESULT_PREFIX + json.dumps(result, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
