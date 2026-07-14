from __future__ import annotations

from pathlib import Path
import signal

from scripts import manage_demo_instance as mgr



def test_discover_demo_api_processes_filters_by_root_and_port(monkeypatch):
    root = Path("/home/weidf/deploy/pytc-client-demo2")
    other_root = Path("/home/weidf/other-project")

    def fake_ps(*_args, **_kwargs):
        return "\n".join(
            [
                "1234 python /tmp/whatever.py",
                "2345 PYTC_API_PORT=4342 python -m server_api.main",
                "3456 PYTC_API_PORT=4343 python -m server_api.main",
                "4567 PYTC_API_PORT=4342 python -m server_api.main",
            ]
        )

    monkeypatch.setattr(mgr.subprocess, "check_output", fake_ps)
    monkeypatch.setattr(mgr, "_read_process_cwd", lambda pid: str({
        2345: str(root),
        3456: str(root),
        4567: str(other_root),
    }[pid]))
    monkeypatch.setattr(
        mgr,
        "_read_process_env",
        lambda pid: {"PYTC_API_PORT": "4342"} if pid == 2345 else {"PYTC_API_PORT": "4343"},
    )

    found = mgr.discover_demo_api_processes(api_port=4342, root=root)
    assert [item.pid for item in found] == [2345]


def test_build_api_command_includes_nohup_and_setsid_and_defaults():
    command, env = mgr._build_api_command(
        python_bin=Path("/home/example/.venv/bin/python"),
        api_port=4342,
    )

    assert command[:2] == ["nohup", "setsid"]
    assert command[-2:] == ["-m", "server_api.main"]
    assert env["PYTC_API_PORT"] == str(mgr.DEMO2_API_PORT)
    assert env["PYTC_WORKER_URL"] == mgr.DEMO2_WORKER_URL
    assert env["PYTC_NEUROGLANCER_PUBLIC_BASE"] == mgr.DEMO2_NEUROGLANCER_PUBLIC_BASE


def test_build_api_command_uses_requested_api_port():
    command, env = mgr._build_api_command(
        python_bin=Path("/home/example/.venv/bin/python"),
        api_port=4567,
    )

    assert command[:2] == ["nohup", "setsid"]
    assert env["PYTC_API_PORT"] == "4567"
    assert env["PYTC_API_HOST"] == "127.0.0.1"


def test_runtime_snapshot_message_includes_runtime_config():
    message = mgr._runtime_snapshot_message(
        {
            "PYTC_WORKER_URL": "localhost:4243",
            "PYTC_NEUROGLANCER_PORT": "4244",
            "PYTC_NEUROGLANCER_PUBLIC_BASE": "https://demo.seg.bio/neuroglancer",
        },
        api_port=4342,
    )
    assert message == (
        "Runtime config -> api_port=4342, "
        "worker_url=localhost:4243, "
        "neuroglancer_port=4244, "
        "neuroglancer_public_base=https://demo.seg.bio/neuroglancer"
    )


def test_parse_extra_env(monkeypatch):
    assert mgr.parse_extra_env(["A=1", " B=2 "]) == {"A": "1", "B": "2"}


def test_stop_demo_api_uses_sigterm_and_returns_success(monkeypatch):
    root = Path("/home/weidf/deploy/pytc-client-demo2")
    processes = [
        mgr.DemoApiProcess(pid=2345, command="python -m server_api.main", cwd=str(root), env={}),
    ]

    killed = []

    def fake_find(*, api_port, root):
        return processes

    def fake_kill(pid, signal_num):
        killed.append((pid, signal_num))

    def fake_is_alive(pid):
        return False

    monkeypatch.setattr(mgr, "discover_demo_api_processes", fake_find)
    monkeypatch.setattr(mgr.os, "kill", fake_kill)
    monkeypatch.setattr(mgr, "_is_process_alive", fake_is_alive)

    result = mgr.stop_demo_api(api_port=4342, root=root)

    assert result == 0
    assert killed == [(2345, signal.SIGTERM)]


def test_main_status_stops_without_disruptive_cleanup_when_not_running(monkeypatch):
    parser_args = ["status", "--api-port", "4342", "--repo-root", "/tmp/demo"]
    monkeypatch.setattr(mgr, "discover_demo_api_processes", lambda *_, **__: [])

    result = mgr.main(parser_args)
    assert result == 1
