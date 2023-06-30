from fastapi import File, UploadFile, FastAPI, Form, Request
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import numpy as np
from utils.io import readVol

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


def start():
    uvicorn.run("main:app", host="127.0.0.1", port=4242, reload=True, log_level="info", app_dir="/")


if __name__ == "__main__":
    start()
