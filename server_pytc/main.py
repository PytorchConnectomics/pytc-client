from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from services.model import start, stop, initialize_tensorboard, get_tensorboard

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
async def start_model_training(req: dict):
    # req = await req.json()
    print("start_model")
    log_dir = req['log_dir']
    start(log_dir)


@app.post("/stop_model_training")
async def stop_model_training():
    print("Stop model training")
    return stop()


@app.get('/start_tensorboard')
async def start_tensorboard():
    return initialize_tensorboard()

@app.get('/get_tensorboard_url')
async def get_tensorboard_url():
    return get_tensorboard()

def run():
    uvicorn.run("main:app", host="127.0.0.1", port=4243, reload=True, log_level="info", app_dir="/")


if __name__ == "__main__":
    run()
