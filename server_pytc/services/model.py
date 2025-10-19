import os
import signal
import subprocess
import tempfile
import psutil
import atexit

# TODO: Global process tracking for proper cleanup
_training_process = None
_inference_process = None
_temp_files = []


def start_training(dict: dict):
    global _training_process
    
    # TODO: Stop existing training process if running
    if _training_process and _training_process.poll() is None:
        print("Stopping existing training process...")
        stop_training()
    
    path = "pytorch_connectomics/scripts/main.py"
    command = ["python", path]

    for key, value in dict["arguments"].items():
        if value is not None:
            command.extend([f"--{key}", str(value)])

    # TODO: Write the value to a temporary file and track it for cleanup
    temp_file = tempfile.NamedTemporaryFile(
        delete=False, mode="w", suffix=".yaml"
    )
    temp_file.write(dict["trainingConfig"])
    temp_filepath = temp_file.name
    temp_file.close()
    _temp_files.append(temp_filepath)
    
    command.extend(["--config-file", str(temp_filepath)])

    # TODO: Execute the command using subprocess.Popen for proper async handling
    print("Starting training with command:", command)
    try:
        _training_process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        print(f"Training process started with PID: {_training_process.pid}")
        
        # Initialize tensorboard asynchronously
        initialize_tensorboard(dict["logPath"])
        print("TensorBoard initialized")
        
        return {"status": "started", "pid": _training_process.pid}
    except Exception as e:
        print(f"Error starting training: {e}")
        # Cleanup temp file if process failed to start
        if os.path.exists(temp_filepath):
            os.unlink(temp_filepath)
            _temp_files.remove(temp_filepath)
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
    from tensorboard import program

    tb = program.TensorBoard()
    # tb.configure(argv=[None, "--logdir", "./logs"])
    try:
        tb.configure(argv=[None, "--logdir", logPath, "--host", "0.0.0.0"])
        tensorboard_url = tb.launch()
        print(f"TensorBoard is running at {tensorboard_url}")
    except Exception as e:
        tensorboard_url = "http://localhost:6006/"
        print(f"TensorBoard is running at {tensorboard_url} due to {e}")
        # return str(url)


def get_tensorboard():
    return tensorboard_url


def stop_tensorboard():
    stop_process_by_name("tensorboard")


def start_inference(dict: dict):
    path = "pytorch_connectomics/scripts/main.py"

    command = ["python", path, "--inference"]

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
