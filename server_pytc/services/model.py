import os
import signal
import subprocess


def start(dict: dict):
    path = '../pytorch_connectomics/scripts/main.py'

    command = ['python', path]

    for key, value in dict['arguments'].items():
        if value is not None:
            command.extend([f"--{key}", str(value)])

    # Execute the command using subprocess.call
    print(command)
    try:
        subprocess.call(command)
    except subprocess.CalledProcessError as e:
        print(f"Error occurred: {e}")

    print("start")
    initialize_tensorboard(dict['logPath'])
    print("initialize_tensorboard")

def stop():
    # running_processes = psutil.process_iter()
    # # Find all Python processes
    # python_processes = [p for p in running_processes if p.name().lower() == 'python']
    # # cmd_to_stop= 'test/mnist.py'# Needs to be replaced by 'pytorch_connectomics/scripts/main.py' once it's used in function start()
    # cmd_to_stop = '../pytorch_connectomics/scripts/main.py'
    # # Find the training process
    # for process in python_processes:
    #   cmdstring=(process.cmdline())
    #   if cmd_to_stop in cmdstring[1]:
    #       process.terminate()
    #       break;
    # return {"stop"}
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
    # Find the process ID of TensorBoard
    # process = subprocess.Popen(['pgrep', '-f', 'tensorboard'], stdout=subprocess.PIPE)
    # output, _ = process.communicate()
    # pid = output.strip().decode()
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

def startInference(dict: dict):
    path = '../pytorch_connectomics/scripts/main.py'

    command = ['python', path]

    for key, value in dict['arguments'].items():
        if value is not None:
            command.extend([f"--{key}", str(value)])

    # Execute the command using subprocess.call
    print(command)
    try:
        subprocess.call(command)
    except subprocess.CalledProcessError as e:
        print(f"Error occurred: {e}")

    print("start")

def stopInference():
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

if __name__ == "__main__":
    start()