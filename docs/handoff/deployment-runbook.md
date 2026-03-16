# Deployment Runbook

## Goal

Bring up a working demo of the app on a remote machine with the least moving parts and the clearest failure modes.

## Recommended Demo Shapes

### Option A: Full stack on the remote machine

Use this when the remote machine has a GUI session and the goal is to demonstrate the actual Electron app.

Pros:

- closest to current local development flow
- no frontend reconfiguration required beyond the existing defaults
- easiest path if the operator is physically on that machine or can remote desktop into it

Cons:

- still a development-style startup path, not a packaged desktop app
- requires Node, uv, Python 3.11, and a usable desktop session

### Option B: Remote backend services plus local client

Use this when the remote machine is mainly for compute and the operator will run the UI locally.

Pros:

- simpler on headless machines
- avoids Electron/desktop issues on the remote host

Cons:

- requires pointing the local frontend to the remote API host
- additional care needed for file paths because the backend and frontend are not on the same filesystem

For a first demo, Option A is the lowest-risk path if the remote machine has a desktop session. For a headless compute node, Option B is more realistic.

## Prerequisites

- Python `3.11`
- `uv`
- `node` and `npm`
- `git`
- OS packages sufficient to run Electron if using Option A
- network access to clone `https://github.com/PytorchConnectomics/pytorch_connectomics.git`

## Code and Dependency Bring-Up

From a fresh machine:

```bash
git clone <this-repo-url>
cd pytc-client
# if this work has not merged to main yet:
git checkout fix/pytc-v2-runtime-and-schema
scripts/bootstrap.sh
```

What `scripts/bootstrap.sh` does:

1. ensures `pytorch_connectomics` is present at the pinned commit from `scripts/setup_pytorch_connectomics.sh`
2. runs `uv sync --python 3.11`
3. runs `npm install` in `client`

## Fastest Full-Stack Bring-Up

```bash
scripts/start.sh
```

Expected services:

- data server on `http://localhost:8000/`
- API server on `http://localhost:4242/health`
- PyTC worker on `http://localhost:4243/hello`
- React dev server on `http://localhost:3000/`
- Electron launched after the services are ready

Logs:

- startup logs go under `.logs/start`
- training and inference logs are also exposed in the app UI and via HTTP routes

## Manual Service Bring-Up

Use this when you want to control the process supervisor yourself instead of using `scripts/start.sh`.

```bash
uv run --directory . python server_api/scripts/serve_data.py
PYTHONDONTWRITEBYTECODE=1 uv run --directory . python -m server_api.main
uv run --directory . python -m server_pytc.main
npm --prefix client start
# if using Electron on the same machine:
npm --prefix client run electron
```

## Health Checks

Check these first before debugging the UI:

```bash
curl -sf http://localhost:8000/
curl -sf http://localhost:4242/health
curl -sf http://localhost:4243/hello
```

Training and inference status endpoints:

```bash
curl -sf http://localhost:4242/training_status
curl -sf http://localhost:4242/inference_status
curl -sf http://localhost:4242/training_logs
curl -sf http://localhost:4242/inference_logs
```

## Demo Smoke Test Guidance

### Training

Requirements:

- a valid training config
- image and label paths that exist on the machine running the backend
- an output directory writable by the backend process

Expected behavior:

- training launch returns quickly
- `training_status` moves into a running state
- `training_logs` and the in-app runtime panel show real subprocess output

### Inference

Requirements:

- a valid inference config
- an existing checkpoint path visible to the backend machine
- valid input paths
- a writable output directory

Expected behavior:

- inference launch returns quickly
- `inference_status` reflects running or completed state
- `inference_logs` and the in-app runtime panel show the real worker output

## File Path Reality Check

This app currently assumes the UI operator and backend process are effectively working against the same filesystem view.

That means:

- Option A is straightforward because the client and backend are on the same machine
- Option B is only safe if the selected paths refer to files that exist on the remote backend host, not just on the local UI host

If you want a reliable first demo, keep the UI and backend on the same machine.

## TensorBoard

Relevant routes:

- `GET /start_tensorboard?logPath=<dir>`
- `GET /get_tensorboard_url`

Default exposed port:

- `6006`

## Docker Notes

There is a `Dockerfile` and `docker-compose.yaml`, but they currently cover backend bring-up only. They do not package the Electron/React desktop flow.

Use Docker only if the deployment target is backend-only or if you are explicitly extending the container setup.

## Recommended First Deployment Sequence

1. clone the repo and check out the deployment branch or merged equivalent
2. run `scripts/bootstrap.sh`
3. run the validation commands from `docs/handoff/validation.md`
4. run `scripts/start.sh`
5. verify health endpoints
6. perform one training smoke and one inference smoke with machine-local paths
7. only after that, decide whether to package, containerize, or split frontend/backend
