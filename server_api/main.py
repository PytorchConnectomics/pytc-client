import json
import pathlib
import shutil
import tempfile
from typing import List, Optional

import requests
import uvicorn
from fastapi import FastAPI, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from utils.io import readVol
from utils.utils import process_path
from chatbot.chatbot import chain, memory
from auth import models, database, router as auth_router
from synanno import router as synanno_router

from fastapi.staticfiles import StaticFiles
import os

REACT_APP_SERVER_PROTOCOL = "http"
REACT_APP_SERVER_URL = "localhost:4243"

models.Base.metadata.create_all(bind=database.engine)

app = FastAPI()

# Ensure uploads directory exists
os.makedirs("uploads", exist_ok=True)
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

app.include_router(auth_router.router)
app.include_router(synanno_router.router, tags=["synanno"])

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def save_upload_to_tempfile(upload: UploadFile) -> pathlib.Path:
    suffix = pathlib.Path(upload.filename or "").suffix
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        upload.file.seek(0)
        shutil.copyfileobj(upload.file, tmp)
        temp_path = pathlib.Path(tmp.name)
    return temp_path


@app.get("/hello")
def hello():
    return {"hello"}


@app.post("/neuroglancer")
async def neuroglancer(req: Request):
    import neuroglancer

    cleanup_paths: List[pathlib.Path] = []
    try:
        content_type = req.headers.get("content-type", "")
        if "multipart/form-data" in content_type:
            form = await req.form()
            image_upload = form.get("image")
            if not image_upload or not getattr(image_upload, "filename", None):
                raise HTTPException(status_code=400, detail="Image file is required.")
            scales_raw = form.get("scales")
            if scales_raw is None:
                raise HTTPException(status_code=400, detail="Scales are required.")
            try:
                scales = json.loads(scales_raw)
            except json.JSONDecodeError:
                raise HTTPException(status_code=400, detail="Scales payload is invalid.")

            image = save_upload_to_tempfile(image_upload)
            cleanup_paths.append(image)

            label_upload = form.get("label")
            label: Optional[pathlib.Path] = None
            if label_upload and getattr(label_upload, "filename", None):
                label = save_upload_to_tempfile(label_upload)
                cleanup_paths.append(label)
        else:
            payload = await req.json()
            image = process_path(payload["image"])
            label = process_path(payload.get("label"))
            scales = payload["scales"]

        print(image, label, scales)

        if image is None:
            raise HTTPException(status_code=400, detail="Image path or file is required.")

        # neuroglancer setting -- bind to this to make accessible outside of container
        ip = "0.0.0.0"
        port = 4244
        neuroglancer.set_server_bind_address(ip, port)
        viewer = neuroglancer.Viewer()
        # SNEMI (# 3d vol dim: z,y,x)
        res = neuroglancer.CoordinateSpace(
            names=["z", "y", "x"], units=["nm", "nm", "nm"], scales=scales
        )
        try:
            im = readVol(image, image_type="im")
            gt = readVol(label, image_type="im") if label else None
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Failed to read image volume: {str(e)}")

        def ngLayer(data, res, oo=[0, 0, 0], tt="segmentation"):
            return neuroglancer.LocalVolume(
                data, dimensions=res, volume_type=tt, voxel_offset=oo
            )

        with viewer.txn() as s:
            s.layers.append(name="im", layer=ngLayer(im, res, tt="image"))
            if gt is not None:
                s.layers.append(name="gt", layer=ngLayer(gt, res, tt="segmentation"))

        print(viewer)
        return str(viewer)
    finally:
        for path in cleanup_paths:
            try:
                path.unlink()
            except FileNotFoundError:
                pass
            except PermissionError:
                pass


@app.post("/start_model_training")
async def start_model_training(req: Request):
    print("\n========== SERVER_API: START_MODEL_TRAINING ENDPOINT CALLED ==========")
    req = await req.json()
    print(f"[SERVER_API] Received request payload keys: {list(req.keys())}")
    print(f"[SERVER_API] Arguments: {req.get('arguments', {})}")
    print(f"[SERVER_API] Log path: {req.get('logPath', 'NOT PROVIDED')}")
    print(f"[SERVER_API] Output path: {req.get('outputPath', 'NOT PROVIDED')}")
    print(f"[SERVER_API] Training config length: {len(req.get('trainingConfig', '')) if req.get('trainingConfig') else 0} chars")
    print(f"[SERVER_API] NOTE: TensorBoard will monitor outputPath where PyTorch Connectomics writes logs")
    
    try:
        target_url = REACT_APP_SERVER_PROTOCOL + "://" + REACT_APP_SERVER_URL + "/start_model_training"
        print(f"[SERVER_API] Proxying to PyTC server at: {target_url}")
        
        response = requests.post(
            target_url,
            json=req,
            timeout=30  # TODO: Add timeout to prevent hanging
        )
        
        print(f"[SERVER_API] PyTC server response status: {response.status_code}")
        print(f"[SERVER_API] PyTC server response: {response.text[:500]}")  # First 500 chars

        if response.status_code == 200:
            print("[SERVER_API] ✓ Training request proxied successfully")
            return {"message": "Model training started successfully", "data": response.json()}
        else:
            print(f"[SERVER_API] ✗ PyTC server returned error status: {response.status_code}")
            return {"message": f"Failed to start model training: {response.status_code}", "error": response.text}
    except requests.exceptions.ConnectionError as e:
        print(f"[SERVER_API] ✗ CONNECTION ERROR: Cannot reach PyTC server at {REACT_APP_SERVER_URL}")
        print(f"[SERVER_API] Error details: {e}")
        return {"message": "Failed to connect to PyTC server. Is server_pytc running?", "error": "ConnectionError"}
    except requests.exceptions.Timeout:
        print("[SERVER_API] ✗ TIMEOUT: PyTC server did not respond within 30 seconds")
        return {"message": "Request timed out. PyTC server may be overloaded.", "error": "Timeout"}
    except Exception as e:
        print(f"[SERVER_API] ✗ UNEXPECTED ERROR: {type(e).__name__}: {str(e)}")
        import traceback
        print(traceback.format_exc())
        return {"message": f"Failed to start model training: {str(e)}", "error": str(e)}
    finally:
        print("========== SERVER_API: END OF START_MODEL_TRAINING ==========\n")


@app.post("/stop_model_training")
async def stop_model_training():
    try:
        response = requests.post(
            REACT_APP_SERVER_PROTOCOL
            + "://"
            + REACT_APP_SERVER_URL
            + "/stop_model_training",
            timeout=30
        )

        if response.status_code == 200:
            return {"message": "Model training stopped successfully", "data": response.json()}
        else:
            return {"message": f"Failed to stop model training: {response.status_code}", "error": response.text}
    except requests.exceptions.ConnectionError:
        return {"message": "Failed to connect to PyTC server. Is server_pytc running?", "error": "ConnectionError"}
    except requests.exceptions.Timeout:
        return {"message": "Request timed out.", "error": "Timeout"}
    except Exception as e:
        return {"message": f"Failed to stop model training: {str(e)}", "error": str(e)}


@app.get("/training_status")
async def get_training_status():
    """Proxy training status check to PyTC server"""
    try:
        response = requests.get(
            REACT_APP_SERVER_PROTOCOL
            + "://"
            + REACT_APP_SERVER_URL
            + "/training_status",
            timeout=5
        )
        return response.json()
    except requests.exceptions.ConnectionError:
        return {"isRunning": False, "error": "Cannot connect to PyTC server"}
    except Exception as e:
        return {"isRunning": False, "error": str(e)}


@app.post("/start_model_inference")
async def start_model_inference(req: Request):
    req = await req.json()
    try:
        response = requests.post(
            REACT_APP_SERVER_PROTOCOL
            + "://"
            + REACT_APP_SERVER_URL
            + "/start_model_inference",
            json=req,
            timeout=30
        )

        if response.status_code == 200:
            return {"message": "Model inference started successfully", "data": response.json()}
        else:
            return {"message": f"Failed to start model inference: {response.status_code}", "error": response.text}
    except requests.exceptions.ConnectionError:
        return {"message": "Failed to connect to PyTC server. Is server_pytc running?", "error": "ConnectionError"}
    except requests.exceptions.Timeout:
        return {"message": "Request timed out. PyTC server may be overloaded.", "error": "Timeout"}
    except Exception as e:
        return {"message": f"Failed to start model inference: {str(e)}", "error": str(e)}


@app.post("/stop_model_inference")
async def stop_model_inference():
    try:
        response = requests.post(
            REACT_APP_SERVER_PROTOCOL
            + "://"
            + REACT_APP_SERVER_URL
            + "/stop_model_inference",
            timeout=30
        )

        if response.status_code == 200:
            return {"message": "Model inference stopped successfully", "data": response.json()}
        else:
            return {"message": f"Failed to stop model inference: {response.status_code}", "error": response.text}
    except requests.exceptions.ConnectionError:
        return {"message": "Failed to connect to PyTC server. Is server_pytc running?", "error": "ConnectionError"}
    except requests.exceptions.Timeout:
        return {"message": "Request timed out.", "error": "Timeout"}
    except Exception as e:
        return {"message": f"Failed to stop model inference: {str(e)}", "error": str(e)}


@app.get("/get_tensorboard_url")
async def get_tensorboard_url():
    return "http://localhost:6006/"
    # response = requests.get(
    #     REACT_APP_SERVER_PROTOCOL +
    #     "://" +
    #     REACT_APP_SERVER_URL +
    #     "/get_tensorboard_url"
    #   )
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


@app.post("/check_files")
async def check_files(req: Request):
    import numpy as np
    import os

    try:
        im = await req.json()
        print(f"Received check_files payload: {im}")
        print(im.get("folderPath"), im.get("name"))
        
        # Use os.path.join for safe path construction
        if "filePath" in im and im["filePath"]:
            image_path = im["filePath"]
        else:
            image_path = os.path.join(im["folderPath"], im["name"])
            
        print(f"Checking file at: {image_path}")
        
        try:
            # Use readVol to support all project-standard formats (TIFF, H5, etc.)
            image_array = readVol(image_path, image_type="im")
        except Exception as e:
             print(f"Failed to read file: {e}")
             return {"error": f"Failed to open image: {str(e)}"}

        # Heuristic for label detection:
        # 1. Must be integer type
        # 2. Low number of unique values (e.g. < 50) relative to size
        # 3. Or explicit binary (0, 255) or (0, 1)
        
        unique_values = np.unique(image_array)
        num_unique = len(unique_values)
        is_integer = np.issubdtype(image_array.dtype, np.integer)
        
        is_label = False
        if is_integer:
            if num_unique < 50:
                is_label = True
            elif np.array_equal(unique_values, np.array([0, 255])) or np.array_equal(unique_values, np.array([0, 1])):
                is_label = True

        if is_label:
            print(f"The image {im['name']} is likely a label (unique values: {num_unique})")
            label = True
        else:
            print(f"The image {im['name']} is likely not a label (unique values: {num_unique})")
            label = False

        return {"label": label}
    except Exception as e:
        return {"error": str(e)}


# Chatbot endpoints
@app.post("/chat/query")
async def chat_query(req: Request):
    body = await req.json()
    query = body.get('query')
    response = chain.invoke({'question': query})['answer']
    return {"response": response}


@app.post("/chat/clear")
async def clear_chat():
    memory.clear()


def run():
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=4242,
        reload=True,
        log_level="info",
        app_dir="/",
    )


if __name__ == "__main__":
    run()
