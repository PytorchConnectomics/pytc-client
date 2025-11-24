import os
import signal
import subprocess
import tempfile
import psutil
import atexit
import sys
import pathlib

# TODO: Global process tracking for proper cleanup
_training_process = None
_inference_process = None
_temp_files = []


import sys
import pathlib

# ... (imports)

def start_training(dict: dict):
    print("\n========== MODEL.PY: START_TRAINING FUNCTION CALLED ==========")
    global _training_process
    
    print(f"[MODEL.PY] Input dict keys: {list(dict.keys())}")
    print(f"[MODEL.PY] Arguments: {dict.get('arguments', {})}")
    print(f"[MODEL.PY] *** Log path from request: {dict.get('logPath', 'NOT PROVIDED')}")
    print(f"[MODEL.PY] Training config length: {len(dict.get('trainingConfig', ''))} chars")
    
    # Parse YAML to show what OUTPUT_PATH is being used
    try:
        import yaml
        config_obj = yaml.safe_load(dict.get('trainingConfig', ''))
        dataset_output_path = config_obj.get('DATASET', {}).get('OUTPUT_PATH', 'NOT SET')
        print(f"[MODEL.PY] *** YAML DATASET.OUTPUT_PATH: {dataset_output_path}")
        print(f"[MODEL.PY] NOTE: PyTorch Connectomics will write checkpoints to OUTPUT_PATH")
        print(f"[MODEL.PY] NOTE: TensorBoard logs should go to logPath")
    except Exception as e:
        print(f"[MODEL.PY] Could not parse YAML to check OUTPUT_PATH: {e}")
    
    # TODO: Stop existing training process if running
    if _training_process and _training_process.poll() is None:
        print("[MODEL.PY] Existing training process detected, stopping it first...")
        stop_training()
    
    # Use absolute path relative to this file
    # server_pytc/services/model.py -> server_pytc/ -> pytc-client/ -> pytorch_connectomics/scripts/main.py
    print("[MODEL.PY] Resolving script path...")
    current_dir = pathlib.Path(__file__).parent.parent.parent
    print(f"[MODEL.PY] Current dir (project root): {current_dir}")
    script_path = current_dir / "pytorch_connectomics" / "scripts" / "main.py"
    print(f"[MODEL.PY] Script path: {script_path}")
    
    if not script_path.exists():
        print(f"[MODEL.PY] ✗ ERROR: Training script not found at {script_path}")
        raise FileNotFoundError(f"Training script not found at {script_path}")
    else:
        print(f"[MODEL.PY] ✓ Training script found")

    print(f"[MODEL.PY] Python executable: {sys.executable}")
    command = [sys.executable, str(script_path)]

    print(f"[MODEL.PY] Processing command-line arguments...")
    for key, value in dict["arguments"].items():
        if value is not None:
            print(f"[MODEL.PY]   Adding --{key} {value}")
            command.extend([f"--{key}", str(value)])

    # TODO: Write the value to a temporary file and track it for cleanup
    print("[MODEL.PY] Creating temporary YAML config file...")
    temp_file = tempfile.NamedTemporaryFile(
        delete=False, mode="w", suffix=".yaml"
    )
    config_content = dict["trainingConfig"]
    print(f"[MODEL.PY] Writing config ({len(config_content)} chars) to temp file...")
    temp_file.write(config_content)
    temp_filepath = temp_file.name
    temp_file.close()
    _temp_files.append(temp_filepath)
    print(f"[MODEL.PY] ✓ Temp config file created at: {temp_filepath}")
    
    # Show first few lines of the temp file for debugging
    with open(temp_filepath, 'r') as f:
        first_lines = ''.join(f.readlines()[:20])
        print(f"[MODEL.PY] Temp file preview (first 20 lines):\n{first_lines}\n")
    
    command.extend(["--config-file", str(temp_filepath)])

    # TODO: Execute the command using subprocess.Popen for proper async handling
    print(f"[MODEL.PY] Final command: {' '.join(command)}")
    print("[MODEL.PY] Starting subprocess...")
    try:
        _training_process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,  # Merge stderr into stdout
            text=True,
            bufsize=1,  # Line buffered
            cwd=str(current_dir)  # Set working directory
        )
        print(f"[MODEL.PY] ✓ Training process started with PID: {_training_process.pid}")
        
        # Start a thread to read and log subprocess output
        import threading
        def log_subprocess_output():
            print(f"[MODEL.PY] === Training subprocess output (PID {_training_process.pid}) ===")
            try:
                for line in _training_process.stdout:
                    print(f"[TRAINING:{_training_process.pid}] {line.rstrip()}")
                
                # Get exit code
                _training_process.wait()
                print(f"[MODEL.PY] === Training subprocess finished with exit code: {_training_process.returncode} ===")
            except Exception as e:
                print(f"[MODEL.PY] Error reading subprocess output: {e}")
        
        output_thread = threading.Thread(target=log_subprocess_output, daemon=True)
        output_thread.start()
        
        # Initialize TensorBoard to monitor the OUTPUT_PATH where PyTorch Connectomics writes logs
        # PyTorch Connectomics writes logs to {OUTPUT_PATH}/log{timestamp}/
        output_path = dict.get("outputPath")
        log_path = dict.get("logPath")
        
        print(f"[MODEL.PY] *** Output path from request: {output_path}")
        print(f"[MODEL.PY] *** Log path from request: {log_path} (for compatibility only)")
        
        if output_path:
            print(f"[MODEL.PY] *** Initializing TensorBoard to monitor: {output_path}")
            print(f"[MODEL.PY] NOTE: PyTorch Connectomics writes logs to {{OUTPUT_PATH}}/log{{timestamp}}/")
            print(f"[MODEL.PY] NOTE: TensorBoard will automatically find event files in subdirectories")
            initialize_tensorboard(output_path)
            print(f"[MODEL.PY] ✓ TensorBoard initialized for directory: {output_path}")
        else:
            print(f"[MODEL.PY] ⚠ WARNING: No outputPath provided, TensorBoard not initialized")
        
        result = {"status": "started", "pid": _training_process.pid}
        print(f"[MODEL.PY] Returning: {result}")
        print("========== MODEL.PY: END OF START_TRAINING ==========\n")
        return result
    except Exception as e:
        print(f"[MODEL.PY] ✗ ERROR starting training process: {type(e).__name__}: {str(e)}")
        import traceback
        print(traceback.format_exc())
        # Cleanup temp file if process failed to start
        if os.path.exists(temp_filepath):
            print(f"[MODEL.PY] Cleaning up temp file: {temp_filepath}")
            os.unlink(temp_filepath)
            _temp_files.remove(temp_filepath)
        print("========== MODEL.PY: END OF START_TRAINING (WITH ERROR) ==========\n")
        raise


def stop_process_by_name(process_name):
    """Stop processes by name using psutil for better reliability"""
    try:
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                if process_name in ' '.join(proc.info['cmdline'] or []):
                    print(f"Terminating process {proc.info['pid']}: {' '.join(proc.info['cmdline'])}")
                    proc.terminate()
                    proc.wait(timeout=10)  # Wait up to 10 seconds for graceful termination
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.TimeoutExpired):
                # Process already terminated or we don't have permission
                continue
    except Exception as e:
        print(f"Error stopping processes by name '{process_name}': {e}")

def cleanup_temp_files():
    """Clean up temporary files created during training/inference"""
    global _temp_files
    for temp_file in _temp_files[:]:  # Create a copy to iterate over
        try:
            if os.path.exists(temp_file):
                os.unlink(temp_file)
                print(f"Cleaned up temp file: {temp_file}")
            _temp_files.remove(temp_file)
        except Exception as e:
            print(f"Error cleaning up temp file {temp_file}: {e}")


def stop_training():
    global _training_process
    
    # TODO: Stop the tracked training process first
    if _training_process and _training_process.poll() is None:
        try:
            print(f"Terminating training process PID: {_training_process.pid}")
            _training_process.terminate()
            _training_process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            print("Force killing training process...")
            _training_process.kill()
            _training_process.wait()
        except Exception as e:
            print(f"Error stopping training process: {e}")
        finally:
            _training_process = None
    
    # Stop any remaining processes by name as fallback
    stop_process_by_name("python pytorch_connectomics/scripts/main.py")
    stop_tensorboard()
    cleanup_temp_files()
    return {"status": "stopped"}


tensorboard_url = None


def initialize_tensorboard(logPath):
    print(f"[MODEL.PY] initialize_tensorboard called with logPath: {logPath}")
    from tensorboard import program

    tb = program.TensorBoard()
    # tb.configure(argv=[None, "--logdir", "./logs"])
    try:
        print(f"[MODEL.PY] Configuring TensorBoard with logdir: {logPath}")
        tb.configure(argv=[None, "--logdir", logPath, "--host", "0.0.0.0"])
        tensorboard_url = tb.launch()
        print(f"[MODEL.PY] ✓ TensorBoard is running at {tensorboard_url}")
    except Exception as e:
        tensorboard_url = "http://localhost:6006/"
        print(f"[MODEL.PY] ⚠ TensorBoard fallback to {tensorboard_url} due to error: {e}")
        # return str(url)


def get_tensorboard():
    return tensorboard_url


def stop_tensorboard():
    stop_process_by_name("tensorboard")


def start_inference(dict: dict):
    # Use absolute path relative to this file
    current_dir = pathlib.Path(__file__).parent.parent.parent
    script_path = current_dir / "pytorch_connectomics" / "scripts" / "main.py"
    
    if not script_path.exists():
        print(f"Error: Inference script not found at {script_path}")
        raise FileNotFoundError(f"Inference script not found at {script_path}")

    command = [sys.executable, str(script_path), "--inference"]

    # Write the value to a temporary file
    with tempfile.NamedTemporaryFile(
        delete=False, mode="w", suffix=".yaml"
    ) as temp_file:
        temp_file.write(dict["inferenceConfig"])
        temp_filepath = temp_file.name
        command.extend(["--config-file", str(temp_filepath)])

    for key, value in dict["arguments"].items():
        if value is not None:
            command.extend([f"--{key}", str(value)])
    # Execute the command using subprocess.call
    print(command)
    try:
        subprocess.call(command)
    except subprocess.CalledProcessError as e:
        print(f"Error occurred: {e}")

    print("start_inference")


def stop_inference():
    process_name = "python pytorch_connectomics/scripts/main.py"
    stop_process(process_name)
    stop_tensorboard()
