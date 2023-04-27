from fastapi import File, UploadFile, FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn


app = FastAPI()


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

@app.post("/neuroglancer")
async def neuroglancer(image: UploadFile = File(...), label: UploadFile = File(...)):
    import neuroglancer
    import numpy as np
    import imageio
    import h5py
    import base64
    import io

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
    try:
        img_data = image.file.read()
        label_data = label.file.read()
    except Exception:
        return {"message": "There was an error uploading the file"}
    finally:
        image.file.close()
        label.file.close()


    im = imageio.volread(img_data)
    if label_data:
        gt = imageio.volread(label_data)

    def ngLayer(data, res, oo=[0, 0, 0], tt='segmentation'):
        return neuroglancer.LocalVolume(data, dimensions=res, volume_type=tt, voxel_offset=oo)

    with viewer.txn() as s:
        s.layers.append(name='im', layer=ngLayer(im, res, tt='image'))
        s.layers.append(name='gt',layer=ngLayer(gt, res,tt='segmentation'))

    print(viewer)
    return str(viewer)


def start():
    uvicorn.run("main:app", host="127.0.0.1", port=4242, reload=True, log_level="info", app_dir="/")

if __name__ == "__main__":
    start()