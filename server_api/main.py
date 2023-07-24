from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from utils.io import readVol
import requests
import os

REACT_APP_SERVER_PROTOCOL='http'
REACT_APP_SERVER_URL='localhost:4243'


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

    print(image, label)

    # neuroglancer setting
    ip = 'localhost'  # or public IP of the machine for sharable display
    port = 9999  # change to an unused port number
    neuroglancer.set_server_bind_address(bind_address=ip, bind_port=port)
    viewer = neuroglancer.Viewer()

    # SNEMI (# 3d vol dim: z,y,x)
    res = neuroglancer.CoordinateSpace(
        names=['z', 'y', 'x'],
        units=['nm', 'nm', 'nm'],
        scales=[30, 6, 6])
    # try:
    #     img_data = file.file.read()
    #     # img_data = image.file.read()
    #     # label_data = label.file.read()
    # except Exception:
    #     return {"message": "There was an error uploading the file"}
    # finally:
    #     file.file.close()
    #     # image.file.close()
    #     # label.file.close()

    # im = imageio.volread(img_data)
    # if label_data:
    #     gt = imageio.volread(label_data)
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
    # print("start_model")
    # log_dir = req['log_dir']
    # start(log_dir)
    # data = {
    #     'log_dir': req['log_dir']
    # }
    response = requests.post(
        # os.environ.get("REACT_APP_SERVER_PROTOCOL") +
        REACT_APP_SERVER_PROTOCOL +
        '://' +
        # os.environ.get("REACT_APP_SERVER_URL") +
        REACT_APP_SERVER_URL +
        "/start_model_training", json=req)

    if response.status_code == 200:
        return {"message": "Model training started successfully"}
    else:
        return {"message": "Failed to start model training"}



@app.post("/stop_model_training")
async def stop_model_training():
    # print("Stop model training")
    # return stop()
    response = requests.post(
        # os.environ.get("REACT_APP_SERVER_PROTOCOL") +
        REACT_APP_SERVER_PROTOCOL +
        '://' +
        # os.environ.get("REACT_APP_SERVER_URL") +
        REACT_APP_SERVER_URL +
        "/stop_model_training")

    if response.status_code == 200:
        return {"message": "Model training stopped successfully"}
    else:
        return {"message": "Failed to stop model training"}


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

def run():
    uvicorn.run("main:app", host="127.0.0.1", port=4242, reload=True, log_level="info", app_dir="/")


if __name__ == "__main__":
    run()
