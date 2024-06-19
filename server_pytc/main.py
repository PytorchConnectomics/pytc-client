from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from services.model import (
    get_tensorboard,
    initialize_tensorboard,
    start_inference,
    start_training,
    stop_inference,
    stop_training,
)

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


@app.post("/start_model_training")
async def start_model_training(req: Request):
    req = await req.json()
    print("start_model")
    # log_dir = req['log_dir']
    start_training(req)


@app.post("/stop_model_training")
async def stop_model_training():
    print("Stop model training")
    return stop_training()


@app.get('/start_tensorboard')
async def start_tensorboard():
    return initialize_tensorboard()

@app.get('/get_tensorboard_url')
async def get_tensorboard_url():
    return get_tensorboard()

@app.post("/start_model_inference")
async def start_model_inference(req: Request):
    req = await req.json()
    print("start model inference")
    # log_dir = req['log_dir']
    start_inference(req)


@app.post("/stop_model_inference")
async def stop_model_inference():
    print("Stop model inference")
    return stop_inference()


def run():
    uvicorn.run("main:app", host="0.0.0.0", port=4243, reload=True, log_level="info", app_dir="/")


if __name__ == "__main__":
    run()
