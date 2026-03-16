# Architecture

## High-Level Topology

The app is a desktop-oriented Electron application backed by two Python services and one local static data server.

### Components

- `client`
  - Electron shell plus React frontend
  - main Electron entrypoint: `client/main.js`
  - frontend API wrapper: `client/src/api.js`
- `server_api`
  - FastAPI service on port `4242`
  - handles app-facing HTTP routes
  - proxies training and inference control requests to `server_pytc`
- `server_pytc`
  - FastAPI worker service on port `4243`
  - spawns `pytorch_connectomics/scripts/main.py`
  - owns training and inference process lifecycle
  - owns runtime log capture and runtime status snapshots
- static data server
  - serves local sample data from `samples_pytc` on port `8000`

## Default Ports

- `3000`: React development server
- `4242`: `server_api`
- `4243`: `server_pytc`
- `6006`: TensorBoard
- `8000`: static sample/data server

## Runtime Flow

### Training

1. UI gathers input paths, output path, optional log path, and a training YAML config.
2. `client/src/api.js` prepares the YAML and posts to `server_api` `POST /start_model_training`.
3. `server_api/main.py` proxies the request to `server_pytc`.
4. `server_pytc/main.py` calls `server_pytc/services/model.py:start_training()`.
5. `model.py` writes a staged runtime config, launches `pytorch_connectomics/scripts/main.py --mode train`, and begins capturing stdout/stderr.
6. The UI polls:
   - `GET /training_status`
   - `GET /training_logs`
7. TensorBoard is launched separately against the resolved output/log directory.

### Inference

1. UI gathers checkpoint path, input paths, output path, and an inference YAML config.
2. `client/src/api.js` prepares the YAML and posts to `server_api` `POST /start_model_inference`.
3. `server_api/main.py` proxies the request to `server_pytc`.
4. `server_pytc/main.py` calls `server_pytc/services/model.py:start_inference()`.
5. `model.py` writes a staged runtime config, launches `pytorch_connectomics/scripts/main.py --mode test`, and begins capturing stdout/stderr.
6. The UI polls:
   - `GET /inference_status`
   - `GET /inference_logs`

## Config Source Model

The app can load config content from:

- a preset in `pytorch_connectomics/tutorials` or `pytorch_connectomics/configs`
- a user-uploaded YAML file

The client tracks both:

- the current YAML text
- the origin path of that YAML

That origin path matters because relative `_base_` references in PyTC v2 configs must be resolved relative to the original config location, not relative to a temp directory.

## Schema Handling

This integration pass supports two config families:

- legacy uppercase schema
- PyTC v2 lowercase schema

Supported client-side mutations use schema-aware helpers in `client/src/configSchema.js`.

Examples:

- training output path
- inference output path
- architecture selection
- selected slider-backed controls
- input image and label path writes for training and inference

Unsupported controls are intentionally disabled when no compatible key exists.

## Deployment-Relevant Constraints

- `client/.env` defaults the frontend to `localhost:4242`
- `server_api` currently proxies to `localhost:4243`
- CORS is permissive in both Python services
- Electron is currently run in development mode via React dev server plus `npm run electron`
- there is no packaged desktop release flow documented in this repo yet
