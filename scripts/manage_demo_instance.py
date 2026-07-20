#!/usr/bin/env python3
"""Operator-level management for the demo2 API process.

This tool intentionally performs only process orchestration and health verification for
`server_api.main` in this checkout. It is scoped to the expected demo2 root and
`PYTC_API_PORT` so restart operations do not cross-kill sibling demo services.
"""

from __future__ import annotations

import argparse
import os
import signal
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests

DEMO_API_ROOT = Path(__file__).resolve().parent.parent
DEMO2_API_PORT = 4342
DEMO2_WORKER_URL = "localhost:4243"
DEMO2_NEUROGLANCER_PORT = 4244
DEMO2_NEUROGLANCER_PUBLIC_BASE = "https://demo.seg.bio/neuroglancer"
DEMO2_ALLOWED_ORIGINS = (
    "https://demo.seg.bio,http://localhost:3000,http://127.0.0.1:3000,null"
)


@dataclass(frozen=True)
class DemoApiProcess:
    pid: int
    command: str
    cwd: str | None = None
    env: dict[str, str] | None = None


def _demo_api_defaults() -> dict[str, str]:
    return {
        "PYTC_API_PORT": str(DEMO2_API_PORT),
        "PYTC_API_HOST": "127.0.0.1",
        "PYTC_WORKER_URL": DEMO2_WORKER_URL,
        "PYTC_NEUROGLANCER_PORT": str(DEMO2_NEUROGLANCER_PORT),
        "PYTC_NEUROGLANCER_PUBLIC_BASE": DEMO2_NEUROGLANCER_PUBLIC_BASE,
        "PYTC_ALLOWED_ORIGINS": DEMO2_ALLOWED_ORIGINS,
    }


def _safe_int(value: str | None) -> int | None:
    if not value:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _is_descendant_path(candidate: str | None, root: Path) -> bool:
    if not candidate:
        return False
    try:
        candidate_path = Path(candidate).resolve()
        resolved_root = root.resolve()
        return candidate_path == resolved_root or candidate_path.is_relative_to(
            resolved_root
        )
    except Exception:
        return False


def _read_process_cwd(pid: int) -> str | None:
    try:
        return os.path.realpath(os.readlink(f"/proc/{pid}/cwd"))
    except Exception:
        return None


def _read_process_env(pid: int) -> dict[str, str]:
    env_path = f"/proc/{pid}/environ"
    env: dict[str, str] = {}
    try:
        raw = Path(env_path).read_bytes()
    except Exception:
        return env

    for item in raw.split(b"\0"):
        if b"=" not in item:
            continue
        key, value = item.split(b"=", 1)
        env[key.decode("utf-8", errors="ignore")] = value.decode(
            "utf-8", errors="ignore"
        )
    return env


def _extract_pid_from_ps_line(line: str) -> tuple[int, str] | None:
    text = line.strip()
    if not text:
        return None
    pid_text, _, command = text.partition(" ")
    if not pid_text.isdigit():
        return None
    return int(pid_text), command.strip()


def _extract_port_from_command(command: str) -> int | None:
    for token in command.split():
        if token.startswith("PYTC_API_PORT="):
            return _safe_int(token.split("=", 1)[1])
    return None


def discover_demo_api_processes(
    *,
    api_port: int,
    root: Path = DEMO_API_ROOT,
    run_ps: Any | None = None,
) -> list[DemoApiProcess]:
    """Find matching API processes for demo2 in this repo checkout."""

    if run_ps is None:
        run_ps = subprocess.check_output

    output = run_ps(["ps", "-eo", "pid=,command=", "-ww"], text=True)
    processes: list[DemoApiProcess] = []
    for line in str(output).splitlines():
        parsed = _extract_pid_from_ps_line(line)
        if not parsed:
            continue

        pid, command = parsed
        if "server_api.main" not in command:
            continue

        cwd = _read_process_cwd(pid)
        if not _is_descendant_path(cwd, root):
            continue

        env = _read_process_env(pid)
        observed_port = _safe_int(env.get("PYTC_API_PORT"))
        if observed_port is None:
            observed_port = _extract_port_from_command(command)

        if observed_port is not None and observed_port != api_port:
            continue

        processes.append(DemoApiProcess(pid=pid, command=command, cwd=cwd, env=env))

    return processes


def _build_api_command(
    *,
    python_bin: Path,
    api_port: int = DEMO2_API_PORT,
) -> tuple[list[str], dict[str, str]]:
    command = ["nohup", "setsid", str(python_bin), "-m", "server_api.main"]
    env = os.environ.copy()
    env.update(_demo_api_defaults())
    env["PYTC_API_PORT"] = str(api_port)
    env["PYTC_API_BASE"] = f"http://{env['PYTC_API_HOST']}:{env['PYTC_API_PORT']}"
    env["PYTC_WORKER_URL"] = env["PYTC_WORKER_URL"]
    return command, env


def _tail_lines(path: Path, max_lines: int = 80) -> str:
    if not path.exists():
        return "(log file does not exist)"

    lines: list[str] = []
    try:
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            for raw in handle:
                lines.append(raw.rstrip("\n"))
    except Exception as exc:
        return f"(unable to read log file {path}: {exc})"

    if len(lines) <= max_lines:
        return "\n".join(lines)
    return "\n".join(lines[-max_lines:])


def _runtime_snapshot_message(env: dict[str, str], *, api_port: int) -> str:
    return (
        "Runtime config -> "
        f"api_port={api_port}, "
        f"worker_url={env.get('PYTC_WORKER_URL')}, "
        f"neuroglancer_port={env.get('PYTC_NEUROGLANCER_PORT')}, "
        f"neuroglancer_public_base={env.get('PYTC_NEUROGLANCER_PUBLIC_BASE')}"
    )


def _wait_for_health(
    url: str, timeout: int = 30
) -> tuple[bool, str | dict[str, Any] | None]:
    deadline = time.time() + timeout
    last_error = None
    while time.time() < deadline:
        try:
            response = requests.get(url, timeout=2)
            if response.status_code != 200:
                last_error = f"HTTP {response.status_code}"
            else:
                return True, response.json() if response.text else None
        except requests.RequestException as exc:
            last_error = f"{type(exc).__name__}: {exc}"
        time.sleep(1)
    return False, last_error


def stop_demo_api(
    *,
    api_port: int = DEMO2_API_PORT,
    root: Path = DEMO_API_ROOT,
    shutdown_timeout: int = 20,
    poll_interval: float = 0.25,
) -> int:
    processes = discover_demo_api_processes(api_port=api_port, root=root)
    if not processes:
        print(f"No matching demo API process found on port {api_port} under {root}")
        return 0

    for process in processes:
        print(f"Stopping pid {process.pid}: {process.command}")
        try:
            os.kill(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            continue
        except Exception as exc:
            print(f"Failed to signal pid {process.pid}: {exc}")
            return 1

    deadline = time.time() + shutdown_timeout
    while time.time() < deadline:
        alive = [p for p in processes if _is_process_alive(p.pid)]
        if not alive:
            print(f"Stopped {len(processes)} demo API process(es)")
            return 0
        time.sleep(poll_interval)

    for process in processes:
        if _is_process_alive(process.pid):
            try:
                os.kill(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                continue
            except Exception as exc:
                print(f"Failed to force-stop pid {process.pid}: {exc}")
                return 1

    print(f"Forcibly stopped {len(processes)} demo API process(es)")
    return 0


def _is_process_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except Exception:
        return False


def start_demo_api(
    *,
    python_bin: Path = DEMO_API_ROOT / ".venv" / "bin" / "python",
    root: Path = DEMO_API_ROOT,
    log_file: Path = DEMO_API_ROOT / ".logs" / "start" / "demo2-api-server.log",
    api_port: int = DEMO2_API_PORT,
    health_timeout: int = 30,
    force: bool = False,
    pid_file: Path = DEMO_API_ROOT / ".logs" / "start" / "demo2-api.pid",
    extra_env: dict[str, str] | None = None,
) -> int:
    if not python_bin.exists():
        print(f"Python executable not found: {python_bin}")
        return 1

    processes = discover_demo_api_processes(api_port=api_port, root=root)
    if processes:
        if force:
            print(
                f"Found {len(processes)} existing process(es) on demo2 port {api_port}; stopping first"
            )
            stop_rc = stop_demo_api(api_port=api_port, root=root)
            if stop_rc != 0:
                return stop_rc
        else:
            details = ", ".join(str(p.pid) for p in processes)
            print(f"Demo2 API already running on {api_port}: pid(s) {details}")
            return 0

    log_file.parent.mkdir(parents=True, exist_ok=True)
    pid_file.parent.mkdir(parents=True, exist_ok=True)

    command, env = _build_api_command(python_bin=python_bin, api_port=api_port)
    if extra_env:
        env.update(extra_env)
    env["PYTC_API_PORT"] = str(api_port)

    with log_file.open("a", encoding="utf-8") as handle:
        try:
            process = subprocess.Popen(
                command,
                cwd=str(root),
                stdout=handle,
                stderr=subprocess.STDOUT,
                env=env,
            )
        except Exception as exc:
            print(f"Failed to start demo2 API process: {exc}")
            return 1

    pid_file.write_text(f"{process.pid}\n", encoding="utf-8")
    print(f"Started demo2 API pid {process.pid}; logs: {log_file}")
    print(_runtime_snapshot_message(env, api_port=api_port))

    healthy, detail = _wait_for_health(
        f"http://127.0.0.1:{api_port}/health", timeout=health_timeout
    )
    if healthy:
        print(f"Health check passed: https://127.0.0.1:{api_port}/health -> {detail}")
        return 0

    print("Health check failed after startup")
    print(f"Last error: {detail}")
    print("Recent log output:")
    print(_tail_lines(log_file))
    stop_demo_api(api_port=api_port, root=root)
    return 1


def print_status(*, api_port: int, root: Path) -> int:
    processes = discover_demo_api_processes(api_port=api_port, root=root)
    if not processes:
        print("demo2 API: stopped")
        return 1

    health_ok, detail = _wait_for_health(
        f"http://127.0.0.1:{api_port}/health", timeout=3
    )
    status = "healthy" if health_ok else "unhealthy"
    for process in processes:
        print(f"demo2 API pid {process.pid} ({status})")
    if not health_ok:
        print(f"Health detail: {detail}")
        return 1
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage the demo2 API runtime process")
    parser.add_argument(
        "action",
        choices=["start", "stop", "restart", "status"],
        help="Action to run",
    )
    parser.add_argument(
        "--api-port",
        type=int,
        default=DEMO2_API_PORT,
        help=f"Expected PYTC_API_PORT for demo2 (default: {DEMO2_API_PORT})",
    )
    parser.add_argument(
        "--repo-root",
        default=str(DEMO_API_ROOT),
        help="Demo repo root to scope process matching",
    )
    parser.add_argument(
        "--python",
        default=str(DEMO_API_ROOT / ".venv" / "bin" / "python"),
        help="Python executable for launching server_api.main",
    )
    parser.add_argument(
        "--log-file",
        default=str(DEMO_API_ROOT / ".logs" / "start" / "demo2-api-server.log"),
        help="Path for API log output",
    )
    parser.add_argument(
        "--pid-file",
        default=str(DEMO_API_ROOT / ".logs" / "start" / "demo2-api.pid"),
        help="Path for pidfile",
    )
    parser.add_argument(
        "--health-timeout",
        type=int,
        default=30,
        help="Seconds to wait for /health before giving up",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Restart by stopping matching processes before start",
    )
    parser.add_argument(
        "--extra-env",
        action="append",
        default=[],
        help="Pass extra KEY=VALUE env into the managed process",
    )
    return parser


def parse_extra_env(values: list[str]) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for item in values:
        if "=" not in item:
            raise ValueError(f"Invalid --extra-env entry: {item}")
        key, value = item.split("=", 1)
        parsed[key.strip()] = value.strip()
    return parsed


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    root = Path(args.repo_root).resolve()
    log_file = Path(args.log_file)
    pid_file = Path(args.pid_file)

    if args.extra_env:
        try:
            env_overrides = parse_extra_env(args.extra_env)
        except ValueError as exc:
            print(exc)
            return 1
    else:
        env_overrides = {}

    if args.action == "start":
        return start_demo_api(
            python_bin=Path(args.python),
            root=root,
            log_file=log_file,
            api_port=args.api_port,
            health_timeout=args.health_timeout,
            force=args.force,
            pid_file=pid_file,
            extra_env=env_overrides,
        )

    if args.action == "stop":
        return stop_demo_api(api_port=args.api_port, root=root)

    if args.action == "restart":
        stop_rc = stop_demo_api(api_port=args.api_port, root=root)
        if stop_rc != 0:
            return stop_rc
        return start_demo_api(
            python_bin=Path(args.python),
            root=root,
            log_file=log_file,
            api_port=args.api_port,
            health_timeout=args.health_timeout,
            force=False,
            pid_file=pid_file,
            extra_env=env_overrides,
        )

    if args.action == "status":
        return print_status(api_port=args.api_port, root=root)

    print(f"Unknown action: {args.action}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
