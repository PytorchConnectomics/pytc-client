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

Next, please move the image and labels that you'd like to train your models off of into the `samples_pytc` folder. 
Afterwards, upload the images as per the prompts on the applicaation.

Below is a link to a video demo: showing how to set up and run the app:
https://www.loom.com/share/b31dfa06c5da45868a456fe4a50a9e9c?sid=63117ccf-00e8-43a9-95d3-bcdfa8234ab9