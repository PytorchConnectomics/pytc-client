import os
import signal
import subprocess
import tempfile

# TODO: Fix this to work with the yaml file path
def start_training(dict: dict):
    path = '../pytorch_connectomics/scripts/main.py'

    command = ['python', path]

    for key, value in dict['arguments'].items():
        if value is not None:
            command.extend([f"--{key}", str(value)])

    # Write the value to a temporary file
    with tempfile.NamedTemporaryFile(delete=False, mode='w', suffix='.yaml') as temp_file:
        temp_file.write(dict['trainingConfig'])
        temp_filepath = temp_file.name
        command.extend(["--config-file", str(temp_filepath)])


    # Execute the command using subprocess.call
    print(command)
    try:
        subprocess.call(command)
    except subprocess.CalledProcessError as e:
        print(f"Error occurred: {e}")

    print("start_training")
    initialize_tensorboard(dict['logPath'])
    print("initialize_tensorboard")

def stop_training():
    import os
    process_name = "python ../pytorch_connectomics/scripts/main.py"
    try:
        process_line = os.popen("ps ax | grep " + process_name + " | grep -v grep")
        print(process_line)
        fields = process_line.split()
        pid = fields[0]
        print(pid)
        os.kill(int(pid), signal.SIGKILL)
        print("Process Successfully Terminated")
    except:
        print("Error Encountered while Running Script")

    stop_tensorboard()

tensorboard_url = None
def initialize_tensorboard(logPath):
    from tensorboard import program

    tb = program.TensorBoard()
    # tb.configure(argv=[None, '--logdir', './logs'])
    try:
        tb.configure(argv=[None, '--logdir', logPath])
        tensorboard_url = tb.launch()
        print(f'TensorBoard is running at {tensorboard_url}')
    except:
        tensorboard_url = "http://localhost:6006/"
    # return str(url)

def get_tensorboard():
    return tensorboard_url


def stop_tensorboard():
    process_name = "tensorboard"
    try:
        process_line = os.popen("ps ax | grep " + process_name + " | grep -v grep")
        print(process_line)
        fields = process_line.split()
        pid = fields[0]
        print(pid)
        os.kill(int(pid), signal.SIGKILL)
        print("Process Successfully Terminated")
    except:
        print("Error Encountered while Running Script")

def start_inference(dict: dict):
    path = '../pytorch_connectomics/scripts/main.py'

    command = ['python', path, '--inference']

    # Write the value to a temporary file
    with tempfile.NamedTemporaryFile(delete=False, mode='w', suffix='.yaml') as temp_file:
        temp_file.write(dict['inferenceConfig'])
        temp_filepath = temp_file.name
        command.extend(["--config-file", str(temp_filepath)])

    for key, value in dict['arguments'].items():
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
    import os
    process_name = "python ../pytorch_connectomics/scripts/main.py"
    try:
        process_line = os.popen("ps ax | grep " + process_name + " | grep -v grep")
        print(process_line)
        fields = process_line.split()
        pid = fields[0]
        print(pid)
        os.kill(int(pid), signal.SIGKILL)
        print("Process Successfully Terminated")
    except:
        print("Error Encountered while Running Script")

    stop_tensorboard()
