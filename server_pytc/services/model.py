import os
import signal
import subprocess
import tempfile


def start_training(dict: dict):
    path = "pytorch_connectomics/scripts/main.py"

    command = ["python", path]

    for key, value in dict["arguments"].items():
        if value is not None:
            command.extend([f"--{key}", str(value)])

    # Write the value to a temporary file
    with tempfile.NamedTemporaryFile(
        delete=False, mode="w", suffix=".yaml"
    ) as temp_file:
        temp_file.write(dict["trainingConfig"])
        temp_filepath = temp_file.name
        command.extend(["--config-file", str(temp_filepath)])

    # Execute the command using subprocess.call
    print(command)
    try:
        subprocess.call(command)
    except subprocess.CalledProcessError as e:
        print(f"Error occurred: {e}")

    print("start_training")
    initialize_tensorboard(dict["logPath"])
    print("initialize_tensorboard")

def stop_process(process_name):
    try:
        process_line = os.popen("ps ax | grep " + process_name + " | grep -v grep")
        print(process_line)
        fields = process_line.split()
        pid = fields[0]
        print(pid)
        os.kill(int(pid), signal.SIGKILL)
        print(f"Process {process_name} Successfully Terminated")
    except Exception as e:
        print(f"Error Encountered while attempting to stop the process: {process_name}, error: {e}")


def stop_training():
    process_name = "python pytorch_connectomics/scripts/main.py"
    stop_process(process_name)
    stop_tensorboard()


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
    process_name = "tensorboard"
    stop_process(process_name)


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
    try:
        process_line = os.popen("ps ax | grep " + process_name + " | grep -v grep")
        print(process_line)
        fields = process_line.split()
        pid = fields[0]
        print(pid)
        os.kill(int(pid), signal.SIGKILL)
        print("Process Successfully Terminated")
    except Exception as e:
        print(f"Error Encountered while Running Script {e}")

    stop_tensorboard()
