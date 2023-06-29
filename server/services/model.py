import os
import signal
import subprocess


def start(log_dir):
    # path = './pytorch_connectomics/scripts/main.py'
    # arguments = [*args]
    # print(args, arguments, path)
    # command = ['python', path] + arguments
    # subprocess.call(command)

    ## MNIST Example
    path = 'server/test/mnist.py'
    command = ['python', path, log_dir]
    subprocess.call(command)

def stop():
    return {"stop"}


def initialize_tensorboard():
    from tensorboard import program

    tb = program.TensorBoard()
    tb.configure(argv=[None, '--logdir', './logs'])
    url = tb.launch()
    print(f'TensorBoard is running at {url}')
    return str(url)


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