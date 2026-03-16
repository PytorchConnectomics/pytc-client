# Validation

Last validated against branch `fix/pytc-v2-runtime-and-schema` at commit `0487b0a`.

## Automated Checks

The following commands passed during the stabilization pass:

```bash
uv run python -m unittest tests.test_pytc_runtime_routes
uv run python -m compileall server_api server_pytc
npm --prefix client run build
```

Notes:

- the frontend build passed with existing lint warnings in unrelated files
- no failing automated checks were left outstanding for the code changed in this branch

## Backend Route Coverage Added

`tests/test_pytc_runtime_routes.py` covers targeted route and worker behavior for:

- `GET /inference_status`
- `GET /training_logs`
- `GET /inference_logs`
- `GET /start_tensorboard` without `logPath`
- API proxy timeout and worker-error propagation
- staged config placement near the config origin path for relative `_base_` support

## Manual Runtime Checks Performed

### Training endpoint path

Observed:

- `POST /start_model_training` worked through `server_api`
- with untouched `tutorials/neuron_snemi.yaml`, training no longer failed on `_base_` resolution
- instead, it failed for the real reason when paths were invalid or missing

### Training with real local dataset paths

Observed on the original development machine:

- after injecting valid local SNEMI dataset paths, training progressed into real PyTorch Lightning startup
- logs showed model creation, startup, sanity check, and `Epoch 0`

### Inference endpoint path

Observed:

- `POST /start_model_inference` worked through `server_api`
- with an intentionally missing checkpoint, inference failed cleanly and the runtime log endpoint surfaced the real error

### Startup UX

Observed:

- `scripts/start.sh` now reuses already healthy services on occupied ports
- service output is redirected into `.logs/start`
- data-server port collisions now surface a clean message instead of a Python traceback

## What to Re-Run on a New Machine

On any remote host, rerun all three automated checks and then do:

1. health checks for `:8000`, `:4242`, and `:4243`
2. one training smoke using machine-local dataset paths
3. one inference smoke using a real checkpoint visible to the backend host
4. one tensorboard start check with a valid `logPath`
