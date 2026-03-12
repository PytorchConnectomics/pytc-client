import atexit
import pathlib
import subprocess
import sys
import tempfile
import threading
from typing import Any

import psutil

# Track spawned processes so we can stop/poll cleanly.
_training_process = None
_inference_process = None
_temp_files: list[str] = []
tensorboard_url = None


def _project_root() -> pathlib.Path:
    return pathlib.Path(__file__).resolve().parent.parent.parent


def _pytc_script_path() -> pathlib.Path:
    script_path = _project_root() / "pytorch_connectomics" / "scripts" / "main.py"
    if not script_path.exists():
        raise FileNotFoundError(f"PyTC script not found at {script_path}")
    return script_path


def _write_temp_config(config_text: str, label: str) -> str:
    if not config_text or not str(config_text).strip():
        raise ValueError(f"{label} config is required")

    with tempfile.NamedTemporaryFile(delete=False, mode="w", suffix=".yaml") as tmp:
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


def _start_logged_process(command: list[str], cwd: pathlib.Path, label: str):
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        cwd=str(cwd),
    )

    def _log_subprocess_output():
        print(f"[MODEL.PY] === {label} subprocess output (PID {process.pid}) ===")
        try:
            if process.stdout is not None:
                for line in process.stdout:
                    print(f"[{label}:{process.pid}] {line.rstrip()}")
            process.wait()
            print(
                f"[MODEL.PY] === {label} subprocess finished with exit code: {process.returncode} ==="
            )
        except Exception as exc:
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

    try:
        current_dir = _project_root()
        script_path = _pytc_script_path()
        temp_filepath = _write_temp_config(config_text, "training")

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
        _training_process = _start_logged_process(command, current_dir, "TRAINING")

        log_dir = _launch_tensorboard(payload.get("outputPath"), config_text, "train")
        if log_dir:
            print(f"[MODEL.PY] TensorBoard monitoring directory: {log_dir}")

        result = {"status": "started", "pid": _training_process.pid}
        print(f"[MODEL.PY] Returning: {result}")
        print("========== MODEL.PY: END OF START_TRAINING ==========\n")
        return result
    except Exception as exc:
        if temp_filepath and temp_filepath in _temp_files:
            cleanup_temp_files()
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
            print(f"Terminating training process PID: {_training_process.pid}")
            _training_process.terminate()
            _training_process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            print("Force killing training process...")
            _training_process.kill()
            _training_process.wait()
        except Exception as exc:
            print(f"Error stopping training process: {exc}")
        finally:
            _training_process = None

    stop_process_by_name("pytorch_connectomics/scripts/main.py")
    stop_tensorboard()
    cleanup_temp_files()
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

    try:
        current_dir = _project_root()
        script_path = _pytc_script_path()
        temp_filepath = _write_temp_config(config_text, "inference")

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
        _inference_process = _start_logged_process(command, current_dir, "INFERENCE")
        result = {"status": "started", "pid": _inference_process.pid}
        print(f"[MODEL.PY] Returning: {result}")
        print("========== MODEL.PY: END OF START_INFERENCE ==========\n")
        return result
    except Exception as exc:
        if temp_filepath and temp_filepath in _temp_files:
            cleanup_temp_files()
        print(f"[MODEL.PY] ✗ ERROR starting inference process: {exc}")
        raise


def stop_inference():
    global _inference_process

    if _inference_process and _inference_process.poll() is None:
        try:
            print(f"Terminating inference process PID: {_inference_process.pid}")
            _inference_process.terminate()
            _inference_process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            print("Force killing inference process...")
            _inference_process.kill()
            _inference_process.wait()
        except Exception as exc:
            print(f"Error stopping inference process: {exc}")
        finally:
            _inference_process = None

    stop_process_by_name("pytorch_connectomics/scripts/main.py")
    stop_tensorboard()
    cleanup_temp_files()
    return {"status": "stopped"}


atexit.register(cleanup_temp_files)
