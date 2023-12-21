# pytc-client

## Docker installation instructions

```bash
# Pull the image (tag 0.0.1 -- subject to change in future versions)
docker pull xbalbinus/pytc-client:0.0.1
# Expose ports to run the backend servers on Docker
docker run -it -p 4242:4242 -p 4243:4243 -p 4244:4244 -p 6006:6006 --shm-size=8g xbalbinus/pytc-client:0.0.1
```

## Installation
0. Create a Virtual Environment
> For Apple Silicon, please install miniforge3 instead of Anaconda

```
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

1. Client
```
cd client
npm install
```

2. API Server:
```
cd server_api
pip install -r requirements.txt
```

3. Pytc-connectomics:

In root folder,
```
git clone https://github.com/zudi-lin/pytorch_connectomics.git
cd pytorch_connectomics
pip install --editable .
```

## Run Project
### To run
```
./start.sh
```
In a separate terminal
```
cd client
npm run electron
```
