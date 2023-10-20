import requests
import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from utils.io import readVol

REACT_APP_SERVER_PROTOCOL = 'http'
REACT_APP_SERVER_URL = 'localhost:4243'

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)


@app.get("/hello")
def hello():
    return {"hello"}


@app.post("/neuroglancer")
async def neuroglancer(req: Request):
    import neuroglancer

    req = await req.json()
    image = req['image']
    label = req['label']
    scales = req['scales']

    print(image, label, scales)

    # neuroglancer setting
    ip = 'localhost'  # or public IP of the machine for sharable display
    port = 9999
    
    neuroglancer.set_server_bind_address(bind_address=ip, bind_port=port)
    viewer = neuroglancer.Viewer()

    # SNEMI (# 3d vol dim: z,y,x)
    res = neuroglancer.CoordinateSpace(
        names = ['z', 'y', 'x'],
        units = ['nm', 'nm', 'nm'],
        scales = scales
    )

    im = readVol(image, image_type="im")
    gt = readVol(label, image_type="im")

    def ngLayer(data, res, oo=[0, 0, 0], tt='segmentation'):
        return neuroglancer.LocalVolume(data, dimensions=res, volume_type=tt, voxel_offset=oo)

    with viewer.txn() as s:
        s.layers.append(name='im', layer=ngLayer(im, res, tt='image'))
        if label:
            s.layers.append(name='gt', layer=ngLayer(gt, res, tt='segmentation'))

    print(viewer)
    return str(viewer)


@app.post("/start_model_training")
async def start_model_training(req: Request):
    req = await req.json()
    response = requests.post(
        REACT_APP_SERVER_PROTOCOL +
        '://' +
        REACT_APP_SERVER_URL +
        "/start_model_training", json=req)

    if response.status_code == 200:
        return {"message": "Model training started successfully"}
    else:
        return {"message": "Failed to start model training"}


@app.post("/stop_model_training")
async def stop_model_training():
    response = requests.post(
        REACT_APP_SERVER_PROTOCOL +
        '://' +
        REACT_APP_SERVER_URL +
        "/stop_model_training")

    if response.status_code == 200:
        return {"message": "Model training stopped successfully"}
    else:
        return {"message": "Failed to stop model training"}


@app.post("/start_model_inference")
async def start_model_inference(req: Request):
    req = await req.json()
    response = requests.post(
        REACT_APP_SERVER_PROTOCOL +
        '://' +
        REACT_APP_SERVER_URL +
        "/start_model_inference", json=req)

    if response.status_code == 200:
        return {"message": "Model inference started successfully"}
    else:
        return {"message": "Failed to start model inference"}


@app.post("/stop_model_inference")
async def stop_model_inference():
    response = requests.post(
        REACT_APP_SERVER_PROTOCOL +
        '://' +
        REACT_APP_SERVER_URL +
        "/stop_model_inference")

    if response.status_code == 200:
        return {"message": "Model inference stopped successfully"}
    else:
        return {"message": "Failed to stop model inference"}


@app.get('/get_tensorboard_url')
async def get_tensorboard_url():
    return "http://localhost:6006/"
    # response = requests.get(
    #     REACT_APP_SERVER_PROTOCOL +
    #     '://' +
    #     REACT_APP_SERVER_URL +
    #     "/get_tensorboard_url")
    #
    # if response.status_code == 200:
    #     # {"message": "Get tensorboard URL successfully"}
    #     print(response.json())
    #     return response.json()
    # else:
    #     # {"message": "Failed to get tensorboard URL"}
    #     return None

# TODO: Improve on this: basic idea: labels are binary -- black or white?
# Check the unique values: Assume that the label should have 0 or 255
# This is temporarily ditched in favor of allowing users to specify whether or not a file is a label or image.
@app.post('/check_files')
async def check_files(req: Request):
    import numpy as np
    from PIL import Image

    try:
        im = await req.json()
        print(im["folderPath"], im["name"])

        image = Image.open(im["folderPath"] + im["name"])

        image_array = np.array(image)

        unique_values = np.unique(image_array)
        is_label = np.array_equal(unique_values, np.array([0, 255]))

        if is_label:
            print("The image is a label")
            label = True
        else:
            print("The image is not a label")
            label = False

        image.close()
        return {"label": label}
    except Exception as e:
        return {"error": str(e)}

def run():
    uvicorn.run("main:app", host="127.0.0.1", port=4242, reload=True, log_level="info", app_dir="/")


if __name__ == "__main__":
    run()
