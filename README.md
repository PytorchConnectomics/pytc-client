# pytc-client

## Docker installation instructions

```bash
# Pull the image (tag 0.0.1 -- subject to change in future versions)
docker pull xbalbinus/pytc-client:0.0.1
# Expose ports to run the backend servers on Docker
docker run -it -p 4242:4242 -p 4243:4243 -p 4244:4244 -p 6006:6006 --shm-size=8g xbalbinus/pytc-client:0.0.1
```

## Installation
0. Create a Virtual Environment via. Conda

```bash
conda create -n pytc python=3.9
conda activate pytc
conda install pytorch torchvision cudatoolkit=11.3 -c pytorch
```

Alternatively, dependencies can be installed with native Python via. the following:

```bash
# Create a venv
python -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install torch torchvision cuda-python
```

In the rare event that your device does not support CUDA, you may run the following respectively:

```bash
# If using a conda environment
conda create -n pytc python=3.9
conda activate pytc
conda install pytorch torchvision

# If installing via native python
python -m venv .venv
source .venv/bin/activate
pip install torch torchvision
```

1. Client
```bash
cd client
npm install
npm run build
```

2. API Server:
```bash
cd server_api
pip install -r requirements.txt
```

3. Pytc-connectomics:

In root folder,
```bash
git clone https://github.com/zudi-lin/pytorch_connectomics.git
cd pytorch_connectomics
pip install --editable .
```

## Run Project
### To run
```bash
# if running on mac or linux:
./start.sh

# if running on windows:
./start.bat

```
In a separate terminal
```bash
cd client
npm run electron
```

Below is a link to a video demo: showing how to set up and run the app:
[video demo](https://www.loom.com/share/45c09b36bf37408fb3e5a9172e427deb?sid=2777bf8f-a705-4d47-b17a-adf882994168)