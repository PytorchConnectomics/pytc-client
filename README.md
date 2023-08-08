# pytc-client

## Installation
0. Create a Virtual Environment
> For Apple Silicon, please install miniforge3 instead of Anaconda

```
conda create -n pytc python=3.9
conda activate pytc
conda install pytorch torchvision cudatoolkit=11.3 -c pytorch
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

4. Pytc-connectomics Server:
```
cd server_pytc
pip install -r requirements.txt
```

## Run Project
### To run in production mode
`./run.sh`

### To run in development mode
1. Client:
```
cd client
npm start
```

2. API Server:
```
cd server_api
python main.py
```

3. Pytc-connectomics Server:
```
cd server_pytc
python main.py
```
