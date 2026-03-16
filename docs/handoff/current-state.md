# Current State

Last updated: 2026-03-16T18:51:35Z

## Branch and Commit Context

- Working branch for the current integration pass: `fix/pytc-v2-runtime-and-schema`
- Latest documented commit: `0487b0a`
- Base branch used during review: `origin/main` at `d9e66e2`
- The branch is pushed to `origin/fix/pytc-v2-runtime-and-schema`
- At the time this handoff was written, the branch had not yet been merged to `main`

## What Changed in This Pass

### Runtime and API stabilization

- fixed training start so preset-loaded YAML is accepted, not just uploaded files
- fixed inference launch contract and added missing validation for config and checkpoint inputs
- added `GET /inference_status` end to end
- added `GET /training_logs` and `GET /inference_logs` end to end
- improved API proxy error propagation so upstream failures keep their non-200 status and actionable detail
- fixed `GET /start_tensorboard` to require `logPath` explicitly instead of surfacing a server-side 500
- fixed tensorboard URL lookup to proxy the worker instead of returning a hardcoded localhost string
- fixed checkpoint picker behavior to use file selection

### Runtime visibility

- added persistent runtime state and line-buffered subprocess log capture in `server_pytc/services/model.py`
- added in-app runtime log panels for both training and inference
- runtime panels now show phase, PID, exit code, command, staged config path, config origin, timestamps, and captured output

### PyTC v2 config handling

- added `client/src/configSchema.js` with schema-aware read/write helpers
- the client now supports both legacy uppercase YAML and PyTC v2 lowercase YAML for the supported controls in this pass
- YAML mutations for architecture, training/inference output paths, and supported slider controls are schema-aware
- unsupported controls are disabled instead of silently writing dead fields

### Config staging and `_base_` resolution

- the worker now accepts `configOriginPath` from the client
- staged runtime configs are written near the original preset/upload path when possible
- this prevents relative `_base_` includes from being resolved against `/tmp` and breaking

### Startup UX

- `scripts/start.sh` now reuses healthy services already bound to the expected ports
- startup output is redirected to `.logs/start`
- readiness checks are explicit for data server, API server, PyTC server, and React
- `server_api/scripts/serve_data.py` now fails gracefully when port `8000` is already in use

## Dependency State

- Python dependency source for PyTC is configured in `pyproject.toml` as an editable local dependency:
  - package name: `pytorch-connectomics`
  - source path: `pytorch_connectomics`
- `scripts/setup_pytorch_connectomics.sh` clones from:
  - `https://github.com/PytorchConnectomics/pytorch_connectomics.git`
- pinned PyTC commit in that script:
  - `0a0dceb`

## Known Good Behaviors Verified During This Pass

- loading a preset-backed YAML no longer fails solely because it was not uploaded as a file
- training no longer fails on relative `_base_` includes caused by temp-file staging in `/tmp`
- with valid dataset paths, training reaches real PyTorch Lightning startup
- inference start and status/log retrieval work end to end
- worker and proxy failures now surface clearly in the UI and API responses

## Important Local-Only Facts

- manual training smoke used a local dataset path on the original development machine:
  - `/Users/adamg/seg.bio/testing_data/snemi`
- do not assume that path exists on a remote machine
- the local repo used during development contained an untracked `pytorch_connectomics/` directory; fresh machines should obtain it via `scripts/setup_pytorch_connectomics.sh`
