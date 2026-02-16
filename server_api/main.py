import json
import pathlib
import re
import shutil
import tempfile
from typing import List, Optional

import requests
import uvicorn
from fastapi import Depends, FastAPI, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from server_api.utils.io import readVol
from server_api.utils.utils import process_path
from server_api.auth import models, database, router as auth_router
from server_api.auth.database import get_db
from server_api.auth.router import get_current_user
from server_api.synanno import router as synanno_router
from server_api.ehtool import router as ehtool_router

from fastapi.staticfiles import StaticFiles
import os

# Chatbot is optional; keep the server running if dependencies or model endpoints
# are unavailable. We initialize lazily on demand.
try:
    from server_api.chatbot.chatbot import build_chain, build_helper_chain
except Exception as exc:  # pragma: no cover - exercised indirectly via endpoints
    build_chain = None
    build_helper_chain = None
    _chatbot_error = exc

chain = None
_reset_search = None

# In-memory LangChain history, keyed by conversation ID for the main chatbot.
# Rebuilt from DB when switching conversations.
_active_convo_id: Optional[int] = None
_chat_history: list = []

# Helper chat (inline "?" popovers) — keyed by taskKey for isolated sessions
_helper_chains = {}  # taskKey -> (agent, reset_fn)
_helper_histories = {}  # taskKey -> list of messages


def _ensure_chatbot():
    global chain, _reset_search, _chatbot_error
    if chain is not None and _reset_search is not None:
        return True
    if build_chain is None:
        return False
    try:
        chain, _reset_search = build_chain()
        _chatbot_error = None
        return True
    except Exception as exc:  # pragma: no cover - runtime config issue
        chain = None
        _reset_search = None
        _chatbot_error = exc
        return False


REACT_APP_SERVER_PROTOCOL = "http"
REACT_APP_SERVER_URL = "localhost:4243"

models.Base.metadata.create_all(bind=database.engine)

app = FastAPI()

# Ensure uploads directory exists
os.makedirs("uploads", exist_ok=True)
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

app.include_router(auth_router.router)
app.include_router(synanno_router.router, tags=["synanno"])
app.include_router(ehtool_router.router, prefix="/eh", tags=["ehtool"])

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"status": "ok"}


BASE_DIR = pathlib.Path(__file__).resolve().parent.parent
PYTC_CONFIG_ROOT = BASE_DIR / "pytorch_connectomics" / "configs"
PYTC_BUILD_FILE = (
    BASE_DIR / "pytorch_connectomics" / "connectomics" / "model" / "build.py"
)


def _list_pytc_configs() -> List[str]:
    if not PYTC_CONFIG_ROOT.exists():
        return []
    return sorted(
        [
            str(path.relative_to(PYTC_CONFIG_ROOT)).replace("\\", "/")
            for path in PYTC_CONFIG_ROOT.rglob("*.yaml")
        ]
    )


def _read_model_architectures() -> List[str]:
    if not PYTC_BUILD_FILE.exists():
        return []
    text = PYTC_BUILD_FILE.read_text(encoding="utf-8", errors="ignore")
    match = re.search(r"MODEL_MAP\s*=\s*{(.*?)}", text, re.S)
    if not match:
        return []
    block = match.group(1)
    keys = re.findall(r"'([^']+)'\s*:", block)
    return sorted(set(keys))


@app.get("/pytc/configs")
def list_pytc_configs():
    configs = _list_pytc_configs()
    if not configs:
        raise HTTPException(status_code=404, detail="No PyTC config presets found.")
    return {"configs": configs}


@app.get("/pytc/config")
def get_pytc_config(path: str):
    if not path:
        raise HTTPException(status_code=400, detail="Config path is required.")
    if ".." in path or path.startswith("/"):
        raise HTTPException(status_code=400, detail="Invalid config path.")
    requested = (PYTC_CONFIG_ROOT / path).resolve()
    if not str(requested).startswith(str(PYTC_CONFIG_ROOT.resolve())):
        raise HTTPException(status_code=400, detail="Invalid config path.")
    if not requested.is_file():
        raise HTTPException(status_code=404, detail="Config not found.")
    if requested.suffix.lower() != ".yaml":
        raise HTTPException(status_code=400, detail="Config must be a YAML file.")
    content = requested.read_text(encoding="utf-8", errors="ignore")
    return {"path": path, "content": content}


@app.get("/pytc/architectures")
def list_pytc_architectures():
    architectures = _read_model_architectures()
    if not architectures:
        raise HTTPException(status_code=404, detail="No model architectures found.")
    return {"architectures": architectures}


def save_upload_to_tempfile(upload: UploadFile) -> pathlib.Path:
    suffix = pathlib.Path(upload.filename or "").suffix
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        upload.file.seek(0)
        shutil.copyfileobj(upload.file, tmp)
        temp_path = pathlib.Path(tmp.name)
    return temp_path


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
                raise HTTPException(
                    status_code=400, detail="Scales payload is invalid."
                )

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
            raise HTTPException(
                status_code=400, detail="Image path or file is required."
            )

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
            raise HTTPException(
                status_code=400, detail=f"Failed to read image volume: {str(e)}"
            )

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
    print(
        f"[SERVER_API] Training config length: {len(req.get('trainingConfig', '')) if req.get('trainingConfig') else 0} chars"
    )
    print(
        f"[SERVER_API] NOTE: TensorBoard will monitor outputPath where PyTorch Connectomics writes logs"
    )

    try:
        target_url = (
            REACT_APP_SERVER_PROTOCOL
            + "://"
            + REACT_APP_SERVER_URL
            + "/start_model_training"
        )
        print(f"[SERVER_API] Proxying to PyTC server at: {target_url}")

        response = requests.post(
            target_url, json=req, timeout=30  # TODO: Add timeout to prevent hanging
        )

        print(f"[SERVER_API] PyTC server response status: {response.status_code}")
        print(
            f"[SERVER_API] PyTC server response: {response.text[:500]}"
        )  # First 500 chars

        if response.status_code == 200:
            print("[SERVER_API] ✓ Training request proxied successfully")
            return {
                "message": "Model training started successfully",
                "data": response.json(),
            }
        else:
            print(
                f"[SERVER_API] ✗ PyTC server returned error status: {response.status_code}"
            )
            return {
                "message": f"Failed to start model training: {response.status_code}",
                "error": response.text,
            }
    except requests.exceptions.ConnectionError as e:
        print(
            f"[SERVER_API] ✗ CONNECTION ERROR: Cannot reach PyTC server at {REACT_APP_SERVER_URL}"
        )
        print(f"[SERVER_API] Error details: {e}")
        return {
            "message": "Failed to connect to PyTC server. Is server_pytc running?",
            "error": "ConnectionError",
        }
    except requests.exceptions.Timeout:
        print("[SERVER_API] ✗ TIMEOUT: PyTC server did not respond within 30 seconds")
        return {
            "message": "Request timed out. PyTC server may be overloaded.",
            "error": "Timeout",
        }
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
            timeout=30,
        )

        if response.status_code == 200:
            return {
                "message": "Model training stopped successfully",
                "data": response.json(),
            }
        else:
            return {
                "message": f"Failed to stop model training: {response.status_code}",
                "error": response.text,
            }
    except requests.exceptions.ConnectionError:
        return {
            "message": "Failed to connect to PyTC server. Is server_pytc running?",
            "error": "ConnectionError",
        }
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
            timeout=5,
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
            timeout=30,
        )

        if response.status_code == 200:
            return {
                "message": "Model inference started successfully",
                "data": response.json(),
            }
        else:
            return {
                "message": f"Failed to start model inference: {response.status_code}",
                "error": response.text,
            }
    except requests.exceptions.ConnectionError:
        return {
            "message": "Failed to connect to PyTC server. Is server_pytc running?",
            "error": "ConnectionError",
        }
    except requests.exceptions.Timeout:
        return {
            "message": "Request timed out. PyTC server may be overloaded.",
            "error": "Timeout",
        }
    except Exception as e:
        return {
            "message": f"Failed to start model inference: {str(e)}",
            "error": str(e),
        }


@app.post("/stop_model_inference")
async def stop_model_inference():
    try:
        response = requests.post(
            REACT_APP_SERVER_PROTOCOL
            + "://"
            + REACT_APP_SERVER_URL
            + "/stop_model_inference",
            timeout=30,
        )

        if response.status_code == 200:
            return {
                "message": "Model inference stopped successfully",
                "data": response.json(),
            }
        else:
            return {
                "message": f"Failed to stop model inference: {response.status_code}",
                "error": response.text,
            }
    except requests.exceptions.ConnectionError:
        return {
            "message": "Failed to connect to PyTC server. Is server_pytc running?",
            "error": "ConnectionError",
        }
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
            elif np.array_equal(unique_values, np.array([0, 255])) or np.array_equal(
                unique_values, np.array([0, 1])
            ):
                is_label = True

        if is_label:
            print(
                f"The image {im['name']} is likely a label (unique values: {num_unique})"
            )
            label = True
        else:
            print(
                f"The image {im['name']} is likely not a label (unique values: {num_unique})"
            )
            label = False

        return {"label": label}
    except Exception as e:
        return {"error": str(e)}


# ── Chat history persistence endpoints ─────────────────────────────────────────

@app.get("/chat/conversations", response_model=List[models.ConversationResponse])
def list_conversations(
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return all conversations for the current user, newest first."""
    return (
        db.query(models.Conversation)
        .filter(models.Conversation.user_id == user.id)
        .order_by(models.Conversation.updated_at.desc())
        .all()
    )


@app.post("/chat/conversations", response_model=models.ConversationDetailResponse)
def create_conversation(
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a new empty conversation."""
    convo = models.Conversation(user_id=user.id, title="New Chat")
    db.add(convo)
    db.commit()
    db.refresh(convo)
    return convo


@app.get(
    "/chat/conversations/{convo_id}",
    response_model=models.ConversationDetailResponse,
)
def get_conversation(
    convo_id: int,
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return a conversation and all its messages."""
    convo = (
        db.query(models.Conversation)
        .filter(
            models.Conversation.id == convo_id,
            models.Conversation.user_id == user.id,
        )
        .first()
    )
    if not convo:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return convo


@app.delete("/chat/conversations/{convo_id}")
def delete_conversation(
    convo_id: int,
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete a conversation and all its messages."""
    convo = (
        db.query(models.Conversation)
        .filter(
            models.Conversation.id == convo_id,
            models.Conversation.user_id == user.id,
        )
        .first()
    )
    if not convo:
        raise HTTPException(status_code=404, detail="Conversation not found")
    db.delete(convo)
    db.commit()
    # Clear in-memory history if we just deleted the active conversation
    global _active_convo_id, _chat_history
    if _active_convo_id == convo_id:
        _active_convo_id = None
        _chat_history.clear()
    return {"message": "Conversation deleted"}


@app.patch(
    "/chat/conversations/{convo_id}",
    response_model=models.ConversationResponse,
)
def update_conversation(
    convo_id: int,
    req_body: dict,
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update a conversation's title."""
    convo = (
        db.query(models.Conversation)
        .filter(
            models.Conversation.id == convo_id,
            models.Conversation.user_id == user.id,
        )
        .first()
    )
    if not convo:
        raise HTTPException(status_code=404, detail="Conversation not found")
    if "title" in req_body:
        convo.title = req_body["title"][:120]  # cap at 120 chars
    db.commit()
    db.refresh(convo)
    return convo


def _load_history_for_convo(convo_id: int, db: Session):
    """Rebuild the in-memory _chat_history from the DB for a given conversation."""
    global _active_convo_id, _chat_history
    if _active_convo_id == convo_id:
        return  # already loaded
    msgs = (
        db.query(models.ChatMessage)
        .filter(models.ChatMessage.conversation_id == convo_id)
        .order_by(models.ChatMessage.created_at)
        .all()
    )
    _chat_history = [{"role": m.role, "content": m.content} for m in msgs]
    _active_convo_id = convo_id


# Chatbot endpoints
@app.post("/chat/query")
async def chat_query(
    req: Request,
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not _ensure_chatbot():
        detail = "Chatbot is not configured"
        if "_chatbot_error" in globals():
            detail = f"{detail}: {_chatbot_error}"
        raise HTTPException(status_code=503, detail=detail)
    body = await req.json()
    query = body.get("query")
    convo_id = body.get("conversationId")
    if not isinstance(query, str) or not query.strip():
        raise HTTPException(status_code=400, detail="Query must be a non-empty string.")

    # Auto-create a conversation if none supplied
    if not convo_id:
        convo = models.Conversation(user_id=user.id, title="New Chat")
        db.add(convo)
        db.commit()
        db.refresh(convo)
        convo_id = convo.id
    else:
        convo = (
            db.query(models.Conversation)
            .filter(
                models.Conversation.id == convo_id,
                models.Conversation.user_id == user.id,
            )
            .first()
        )
        if not convo:
            raise HTTPException(status_code=404, detail="Conversation not found")

    # Rebuild in-memory history from DB when switching conversations
    _load_history_for_convo(convo_id, db)

    if _reset_search is not None:
        _reset_search()
    all_messages = _chat_history + [{"role": "user", "content": query}]
    result = chain.invoke({"messages": all_messages})
    messages = result.get("messages", [])
    response = messages[-1].content if messages else "No response generated"

    # Persist to DB
    db.add(models.ChatMessage(conversation_id=convo_id, role="user", content=query))
    db.add(models.ChatMessage(conversation_id=convo_id, role="assistant", content=response))

    # Auto-title: first user message becomes the title (truncated)
    if convo.title == "New Chat":
        convo.title = query[:120].strip() or "New Chat"

    db.commit()

    # Update in-memory history
    _chat_history.append({"role": "user", "content": query})
    _chat_history.append({"role": "assistant", "content": response})

    return {"response": response, "conversationId": convo_id}


@app.post("/chat/clear")
async def clear_chat(
    user: models.User = Depends(get_current_user),
):
    """Reset the in-memory LangChain context (does NOT delete DB messages)."""
    global _active_convo_id, _chat_history
    if not _ensure_chatbot():
        detail = "Chatbot is not configured"
        if "_chatbot_error" in globals():
            detail = f"{detail}: {_chatbot_error}"
        raise HTTPException(status_code=503, detail=detail)
    if _reset_search is not None:
        _reset_search()
    _chat_history.clear()
    _active_convo_id = None
    return {"message": "Chat session reset"}


@app.get("/chat/status")
async def chat_status():
    configured = _ensure_chatbot()
    detail = None
    if not configured and "_chatbot_error" in globals():
        detail = str(_chatbot_error)
    return {"configured": configured, "error": detail}


# ---------------------------------------------------------------------------
# Helper chat endpoints (inline "?" popovers — RAG only, no training/inference)
# ---------------------------------------------------------------------------

def _ensure_helper_chat(task_key: str):
    """Lazily build a helper agent for *task_key*, reusing it on subsequent calls."""
    global _chatbot_error
    if task_key in _helper_chains:
        return True
    if build_helper_chain is None:
        return False
    try:
        agent, reset_fn = build_helper_chain()
        _helper_chains[task_key] = (agent, reset_fn)
        _helper_histories[task_key] = []
        return True
    except Exception as exc:
        _chatbot_error = exc
        return False


@app.post("/chat/helper/query")
async def chat_helper_query(req: Request):
    body = await req.json()
    task_key = body.get("taskKey")
    query = body.get("query")
    field_context = body.get("fieldContext", "")

    if not task_key:
        raise HTTPException(status_code=400, detail="taskKey is required")
    if not isinstance(query, str) or not query.strip():
        raise HTTPException(status_code=400, detail="query must be a non-empty string.")

    if not _ensure_helper_chat(task_key):
        detail = "Helper chatbot is not configured"
        if "_chatbot_error" in globals():
            detail = f"{detail}: {_chatbot_error}"
        raise HTTPException(status_code=503, detail=detail)

    agent, reset_fn = _helper_chains[task_key]
    history = _helper_histories[task_key]

    # Prepend field context to the first message so the LLM knows what field
    # the user is looking at.
    user_content = f"[Field context: {field_context}]\n\n{query}" if field_context else query

    reset_fn()
    all_messages = history + [{"role": "user", "content": user_content}]
    result = agent.invoke({"messages": all_messages})
    messages = result.get("messages", [])
    response = messages[-1].content if messages else "No response generated"
    history.append({"role": "user", "content": user_content})
    history.append({"role": "assistant", "content": response})
    return {"response": response}


@app.post("/chat/helper/clear")
async def chat_helper_clear(req: Request):
    body = await req.json()
    task_key = body.get("taskKey")
    if task_key and task_key in _helper_histories:
        _helper_histories[task_key].clear()
    return {"message": "Helper chat cleared"}


def run():
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=4242,
        reload=False,  # Temporarily disabled to force fresh load
        log_level="info",
    )


if __name__ == "__main__":
    run()
