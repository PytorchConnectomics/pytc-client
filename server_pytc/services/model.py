import os
import signal
import subprocess
import psutil


def start(dict: dict):
    path = '../pytorch_connectomics/scripts/main.py'

    command = ['python', path]

    for key, value in dict.items():
        if value is not None:
            command.extend([f"--{key}", str(value)])

    # Execute the command using subprocess.call
    print(command)
    try:
        subprocess.call(command)
    except subprocess.CalledProcessError as e:
        print(f"Error occurred: {e}")

    print("start")
    initialize_tensorboard()
    print("initialize_tensorboard")

def stop():
    running_processes = psutil.process_iter()
    # Find all Python processes
    python_processes = [p for p in running_processes if p.name().lower() == 'python']
    # cmd_to_stop= 'test/mnist.py'# Needs to be replaced by 'pytorch_connectomics/scripts/main.py' once it's used in function start()
    cmd_to_stop = '../pytorch_connectomics/scripts/main.py'
    # Find the training process
    for process in python_processes:
      cmdstring=(process.cmdline())
      if cmd_to_stop in cmdstring[1]:
          process.terminate()
          break;
    return {"stop"}

tensorboard_url = None
def initialize_tensorboard():
    from tensorboard import program

    tb = program.TensorBoard()
    tb.configure(argv=[None, '--logdir', './logs'])
    tensorboard_url = tb.launch()
    print(f'TensorBoard is running at {tensorboard_url}')
    # return str(url)

def get_tensorboard():
    return tensorboard_url


def stop_tensorboard():
    # Find the process ID of TensorBoard
    process = subprocess.Popen(['pgrep', '-f', 'tensorboard'], stdout=subprocess.PIPE)
    output, _ = process.communicate()
    pid = output.strip().decode()

    # Kill the TensorBoard process
    if pid:
        os.kill(int(pid), signal.SIGTERM)
        print("TensorBoard stopped.")
    else:
        print("TensorBoard is not currently running.")

if __name__ == "__main__":
    start()