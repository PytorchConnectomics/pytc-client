import atexit
import pathlib
import subprocess
import sys
import tempfile
import threading
from collections import deque
from datetime import datetime, timezone
from typing import Any

import psutil

# Track spawned processes so we can stop/poll cleanly.
_training_process = None
_inference_process = None
_temp_files: list[str] = []
tensorboard_url = None
_RUNTIME_LOG_LIMIT = 2000
_runtime_lock = threading.Lock()


def _new_runtime_state():
    return {
        "lines": deque(maxlen=_RUNTIME_LOG_LIMIT),
        "lineCount": 0,
        "phase": "idle",
        "pid": None,
        "exitCode": None,
        "command": None,
        "cwd": None,
        "configPath": None,
        "configOriginPath": None,
        "startedAt": None,
        "endedAt": None,
        "lastUpdatedAt": None,
        "lastError": None,
        "metadata": {},
    }


_runtime_state = {
    "training": _new_runtime_state(),
    "inference": _new_runtime_state(),
}


def _project_root() -> pathlib.Path:
    return pathlib.Path(__file__).resolve().parent.parent.parent


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _get_runtime_process(kind: str):
    if kind == "training":
        return _training_process
    return _inference_process


def _clear_runtime_process(kind: str, process=None):
    global _training_process, _inference_process

    if kind == "training":
        if process is None or _training_process is process:
            _training_process = None
        return

    if process is None or _inference_process is process:
        _inference_process = None


def _reset_runtime_state(kind: str, *, phase: str = "idle", metadata: dict | None = None):
    state = _new_runtime_state()
    timestamp = _utc_now()
    state["phase"] = phase
    state["startedAt"] = timestamp if phase != "idle" else None
    state["lastUpdatedAt"] = timestamp
    state["metadata"] = metadata or {}
    with _runtime_lock:
        _runtime_state[kind] = state


def _update_runtime_state(kind: str, **updates):
    with _runtime_lock:
        state = _runtime_state[kind]
        for key, value in updates.items():
            if key == "metadata" and isinstance(value, dict):
                state["metadata"] = value
            else:
                state[key] = value
        state["lastUpdatedAt"] = _utc_now()


def _append_runtime_log(kind: str, line: str):
    timestamp = _utc_now()
    text = "" if line is None else str(line).rstrip("\n")
    entry = f"[{timestamp}] {text}" if text else f"[{timestamp}]"
    with _runtime_lock:
        state = _runtime_state[kind]
        state["lines"].append(entry)
        state["lineCount"] += 1
        state["lastUpdatedAt"] = timestamp


def _append_runtime_event(kind: str, message: str):
    _append_runtime_log(kind, f"[MODEL.PY] {message}")


def _set_runtime_error(kind: str, message: str):
    _update_runtime_state(kind, lastError=message)
    _append_runtime_event(kind, f"ERROR: {message}")


def _get_runtime_snapshot(kind: str) -> dict[str, Any]:
    process = _get_runtime_process(kind)
    is_running = bool(process and process.poll() is None)
    with _runtime_lock:
        state = _runtime_state[kind]
        lines = list(state["lines"])
        snapshot = {
            "isRunning": is_running,
            "phase": state["phase"],
            "pid": process.pid if is_running else state["pid"],
            "exitCode": state["exitCode"],
            "command": state["command"],
            "cwd": state["cwd"],
            "configPath": state["configPath"],
            "configOriginPath": state["configOriginPath"],
            "startedAt": state["startedAt"],
            "endedAt": state["endedAt"],
            "lastUpdatedAt": state["lastUpdatedAt"],
            "lineCount": state["lineCount"],
            "lastError": state["lastError"],
            "metadata": dict(state["metadata"]),
            "lines": lines,
            "text": "\n".join(lines),
        }
    return snapshot


def _pytc_script_path() -> pathlib.Path:
    script_path = _project_root() / "pytorch_connectomics" / "scripts" / "main.py"
    if not script_path.exists():
        raise FileNotFoundError(f"PyTC script not found at {script_path}")
    return script_path


def _resolve_config_origin_path(config_origin_path: str | None) -> pathlib.Path | None:
    if not config_origin_path:
        return None

    candidate = pathlib.Path(str(config_origin_path).strip())
    if not str(candidate):
        return None

    if candidate.is_absolute():
        resolved = candidate.resolve()
        return resolved if resolved.exists() else None

    pytc_root = _project_root() / "pytorch_connectomics"
    resolved = (pytc_root / candidate).resolve()
    try:
        resolved.relative_to(pytc_root.resolve())
    except ValueError:
        return None
    return resolved if resolved.exists() else None


def _write_temp_config(
    config_text: str, label: str, config_origin_path: str | None = None
) -> str:
    if not config_text or not str(config_text).strip():
        raise ValueError(f"{label} config is required")

    origin = _resolve_config_origin_path(config_origin_path)
    suffix = origin.suffix if origin and origin.suffix else ".yaml"
    temp_kwargs = {"delete": False, "mode": "w", "suffix": suffix}
    if origin is not None:
        temp_kwargs["dir"] = str(origin.parent)
        temp_kwargs["prefix"] = f".__pytc_runtime_{label}_"

    try:
        with tempfile.NamedTemporaryFile(**temp_kwargs) as tmp:
            tmp.write(config_text)
            path = tmp.name
    except OSError:
        with tempfile.NamedTemporaryFile(delete=False, mode="w", suffix=suffix) as tmp:
            tmp.write(config_text)
            path = tmp.name

    _temp_files.append(path)
    return path


def _build_cli_arguments(
    arguments: dict[str, Any], blocked_flags: set[str] | None = None
) -> list[str]:
    blocked = {flag.lower().replace("_", "-") for flag in (blocked_flags or set())}
    cli_args: list[str] = []

    for key, value in (arguments or {}).items():
        if value is None or value == "":
            continue

        flag_name = str(key).strip().replace("_", "-").lower()
        if not flag_name or flag_name in blocked:
            continue
        flag = f"--{flag_name}"

        if isinstance(value, bool):
            if value:
                cli_args.append(flag)
            continue

        if isinstance(value, (list, tuple)):
            for item in value:
                cli_args.extend([flag, str(item)])
            continue

        cli_args.extend([flag, str(value)])

    return cli_args


def _start_logged_process(command: list[str], cwd: pathlib.Path, label: str, kind: str):
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        cwd=str(cwd),
    )
    _update_runtime_state(
        kind,
        phase="running",
        pid=process.pid,
        command=" ".join(command),
        cwd=str(cwd),
        exitCode=None,
        endedAt=None,
        lastError=None,
    )
    _append_runtime_event(kind, f"Spawned {label.lower()} process PID {process.pid}")

    def _log_subprocess_output():
        print(f"[MODEL.PY] === {label} subprocess output (PID {process.pid}) ===")
        try:
            if process.stdout is not None:
                for line in process.stdout:
                    _append_runtime_log(kind, line.rstrip())
                    print(f"[{label}:{process.pid}] {line.rstrip()}")
            process.wait()
            exit_code = process.returncode
            _update_runtime_state(
                kind,
                phase="finished" if exit_code == 0 else "failed",
                exitCode=exit_code,
                endedAt=_utc_now(),
            )
            _append_runtime_event(
                kind,
                f"{label} subprocess finished with exit code: {exit_code}",
            )
            _clear_runtime_process(kind, process)
            print(
                f"[MODEL.PY] === {label} subprocess finished with exit code: {process.returncode} ==="
            )
        except Exception as exc:
            _set_runtime_error(kind, f"Error reading {label} subprocess output: {exc}")
            print(f"[MODEL.PY] Error reading {label} subprocess output: {exc}")

    threading.Thread(target=_log_subprocess_output, daemon=True).start()
    return process


def _extract_output_path_from_yaml(config_text: str, mode: str) -> str | None:
    try:
        import yaml
    except Exception:
        return None

    try:
        config_obj = yaml.safe_load(config_text) or {}
    except Exception:
        return None

    if not isinstance(config_obj, dict):
        return None

    if mode == "train":
        legacy = config_obj.get("DATASET", {}).get("OUTPUT_PATH")
        if legacy:
            return str(legacy)

        modern_dir = config_obj.get("monitor", {}).get("checkpoint", {}).get("dirpath")
        if modern_dir:
            return str(pathlib.Path(str(modern_dir)).parent)

    if mode == "test":
        legacy = config_obj.get("INFERENCE", {}).get("OUTPUT_PATH")
        if legacy:
            return str(legacy)

        modern_dir = (
            config_obj.get("inference", {})
            .get("save_prediction", {})
            .get("output_path")
        )
        if modern_dir:
            return str(modern_dir)

    return None


def _launch_tensorboard(log_dir: str | None, config_text: str, mode: str):
    resolved = log_dir or _extract_output_path_from_yaml(config_text, mode)
    if resolved:
        initialize_tensorboard(resolved)
    return resolved


def start_training(payload: dict):
    print("\n========== MODEL.PY: START_TRAINING FUNCTION CALLED ==========")
    global _training_process

    print(f"[MODEL.PY] Input dict keys: {list(payload.keys())}")
    print(f"[MODEL.PY] Arguments: {payload.get('arguments', {})}")

    if _training_process and _training_process.poll() is None:
        print("[MODEL.PY] Existing training process detected, stopping it first...")
        stop_training()

    config_text = payload.get("trainingConfig", "")
    temp_filepath = None
    config_origin_path = payload.get("configOriginPath")
    _reset_runtime_state(
        "training",
        phase="starting",
        metadata={
            "label": "training",
            "outputPath": payload.get("outputPath"),
            "logPath": payload.get("logPath"),
        },
    )

    try:
        current_dir = _project_root()
        script_path = _pytc_script_path()
        temp_filepath = _write_temp_config(
            config_text,
            "training",
            config_origin_path=config_origin_path,
        )
        _update_runtime_state(
            "training",
            configPath=temp_filepath,
            configOriginPath=config_origin_path,
        )
        _append_runtime_event("training", f"Config origin: {config_origin_path or 'none'}")
        _append_runtime_event("training", f"Staged config path: {temp_filepath}")

        command = [
            sys.executable,
            str(script_path),
            "--config",
            temp_filepath,
            "--mode",
            "train",
        ]
        command.extend(
            _build_cli_arguments(
                payload.get("arguments", {}),
                blocked_flags={"config", "config-file", "mode", "inference"},
            )
        )

        print(f"[MODEL.PY] Final training command: {' '.join(command)}")
        _append_runtime_event("training", f"Final training command: {' '.join(command)}")
        _training_process = _start_logged_process(
            command,
            current_dir,
            "TRAINING",
            "training",
        )

        log_dir = _launch_tensorboard(payload.get("outputPath"), config_text, "train")
        if log_dir:
            _append_runtime_event("training", f"TensorBoard log dir: {log_dir}")
            print(f"[MODEL.PY] TensorBoard monitoring directory: {log_dir}")

        result = {"status": "started", "pid": _training_process.pid}
        print(f"[MODEL.PY] Returning: {result}")
        print("========== MODEL.PY: END OF START_TRAINING ==========\n")
        return result
    except Exception as exc:
        if temp_filepath and temp_filepath in _temp_files:
            cleanup_temp_files()
        _update_runtime_state("training", phase="failed", endedAt=_utc_now())
        _set_runtime_error("training", str(exc))
        print(f"[MODEL.PY] ✗ ERROR starting training process: {exc}")
        raise


def stop_process_by_name(process_name):
    """Stop processes by command substring using psutil."""
    try:
        for proc in psutil.process_iter(["pid", "name", "cmdline"]):
            try:
                if process_name in " ".join(proc.info["cmdline"] or []):
                    print(
                        f"Terminating process {proc.info['pid']}: {' '.join(proc.info['cmdline'])}"
                    )
                    proc.terminate()
                    proc.wait(timeout=10)
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.TimeoutExpired):
                continue
    except Exception as exc:
        print(f"Error stopping processes by name '{process_name}': {exc}")


def cleanup_temp_files():
    """Clean up temporary files created during training/inference."""
    global _temp_files
    for temp_file in _temp_files[:]:
        try:
            pathlib.Path(temp_file).unlink(missing_ok=True)
            _temp_files.remove(temp_file)
        except Exception as exc:
            print(f"Error cleaning up temp file {temp_file}: {exc}")


def stop_training():
    global _training_process

    if _training_process and _training_process.poll() is None:
        try:
            _append_runtime_event(
                "training", f"Terminating training process PID: {_training_process.pid}"
            )
            print(f"Terminating training process PID: {_training_process.pid}")
            _training_process.terminate()
            _training_process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            _append_runtime_event("training", "Force killing training process")
            print("Force killing training process...")
            _training_process.kill()
            _training_process.wait()
        except Exception as exc:
            _set_runtime_error("training", f"Error stopping training process: {exc}")
            print(f"Error stopping training process: {exc}")
        finally:
            _training_process = None

    stop_process_by_name("pytorch_connectomics/scripts/main.py --mode train")
    stop_tensorboard()
    cleanup_temp_files()
    _update_runtime_state("training", phase="stopped", endedAt=_utc_now())
    _append_runtime_event("training", "Training stop requested")
    return {"status": "stopped"}


def initialize_tensorboard(logPath):
    global tensorboard_url

    print(f"[MODEL.PY] initialize_tensorboard called with logPath: {logPath}")
    from tensorboard import program

    tb = program.TensorBoard()
    try:
        tb.configure(argv=[None, "--logdir", logPath, "--host", "0.0.0.0"])
        tensorboard_url = tb.launch()
        print(f"[MODEL.PY] ✓ TensorBoard is running at {tensorboard_url}")
    except Exception as exc:
        tensorboard_url = "http://localhost:6006/"
        print(
            f"[MODEL.PY] ⚠ TensorBoard fallback to {tensorboard_url} due to error: {exc}"
        )


def get_tensorboard():
    return tensorboard_url


def stop_tensorboard():
    stop_process_by_name("tensorboard")


def start_inference(payload: dict):
    print("\n========== MODEL.PY: START_INFERENCE FUNCTION CALLED ==========")
    global _inference_process

    if _inference_process and _inference_process.poll() is None:
        print("[MODEL.PY] Existing inference process detected, stopping it first...")
        stop_inference()

    config_text = payload.get("inferenceConfig", "")
    temp_filepath = None
    config_origin_path = payload.get("configOriginPath")
    _reset_runtime_state(
        "inference",
        phase="starting",
        metadata={
            "label": "inference",
            "outputPath": payload.get("outputPath"),
            "checkpointPath": payload.get("checkpointPath"),
        },
    )

    try:
        current_dir = _project_root()
        script_path = _pytc_script_path()
        temp_filepath = _write_temp_config(
            config_text,
            "inference",
            config_origin_path=config_origin_path,
        )
        _update_runtime_state(
            "inference",
            configPath=temp_filepath,
            configOriginPath=config_origin_path,
        )
        _append_runtime_event(
            "inference", f"Config origin: {config_origin_path or 'none'}"
        )
        _append_runtime_event("inference", f"Staged config path: {temp_filepath}")

        arguments = dict(payload.get("arguments") or {})
        if payload.get("checkpointPath") and not arguments.get("checkpoint"):
            arguments["checkpoint"] = payload["checkpointPath"]

        command = [
            sys.executable,
            str(script_path),
            "--config",
            temp_filepath,
            "--mode",
            "test",
        ]
        command.extend(
            _build_cli_arguments(
                arguments,
                blocked_flags={"config", "config-file", "mode", "inference"},
            )
        )

        print(f"[MODEL.PY] Final inference command: {' '.join(command)}")
        _append_runtime_event("inference", f"Final inference command: {' '.join(command)}")
        _inference_process = _start_logged_process(
            command,
            current_dir,
            "INFERENCE",
            "inference",
        )
        result = {"status": "started", "pid": _inference_process.pid}
        print(f"[MODEL.PY] Returning: {result}")
        print("========== MODEL.PY: END OF START_INFERENCE ==========\n")
        return result
    except Exception as exc:
        if temp_filepath and temp_filepath in _temp_files:
            cleanup_temp_files()
        _update_runtime_state("inference", phase="failed", endedAt=_utc_now())
        _set_runtime_error("inference", str(exc))
        print(f"[MODEL.PY] ✗ ERROR starting inference process: {exc}")
        raise


def get_training_status():
    snapshot = _get_runtime_snapshot("training")
    return {
        "isRunning": snapshot["isRunning"],
        "pid": snapshot["pid"],
        "exitCode": snapshot["exitCode"],
        "phase": snapshot["phase"],
        "lastError": snapshot["lastError"],
    }


def get_inference_status():
    snapshot = _get_runtime_snapshot("inference")
    return {
        "isRunning": snapshot["isRunning"],
        "pid": snapshot["pid"],
        "exitCode": snapshot["exitCode"],
        "phase": snapshot["phase"],
        "lastError": snapshot["lastError"],
    }


def get_training_logs():
    return _get_runtime_snapshot("training")


def get_inference_logs():
    return _get_runtime_snapshot("inference")


def stop_inference():
    global _inference_process

    if _inference_process and _inference_process.poll() is None:
        try:
            _append_runtime_event(
                "inference", f"Terminating inference process PID: {_inference_process.pid}"
            )
            print(f"Terminating inference process PID: {_inference_process.pid}")
            _inference_process.terminate()
            _inference_process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            _append_runtime_event("inference", "Force killing inference process")
            print("Force killing inference process...")
            _inference_process.kill()
            _inference_process.wait()
        except Exception as exc:
            _set_runtime_error("inference", f"Error stopping inference process: {exc}")
            print(f"Error stopping inference process: {exc}")
        finally:
            _inference_process = None

    stop_process_by_name("pytorch_connectomics/scripts/main.py --mode test")
    stop_tensorboard()
    cleanup_temp_files()
    _update_runtime_state("inference", phase="stopped", endedAt=_utc_now())
    _append_runtime_event("inference", "Inference stop requested")
    return {"status": "stopped"}


atexit.register(cleanup_temp_files)
