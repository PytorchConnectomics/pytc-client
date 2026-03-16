# Environment Notes

## Frontend

Current committed client env file:

- `client/.env`

Current values:

```env
REACT_APP_SERVER_PROTOCOL=http
REACT_APP_SERVER_URL=localhost:4242
```

Meaning:

- the React/Electron client will call `server_api` on `localhost:4242` unless changed

For a remote backend plus local client setup, this value must point at the remote API host, for example:

```env
REACT_APP_SERVER_PROTOCOL=http
REACT_APP_SERVER_URL=<remote-host>:4242
```

## API to Worker

`server_api/main.py` currently proxies model operations to:

- protocol: `http`
- host: `localhost:4243`

If `server_api` and `server_pytc` do not run on the same machine, that file must be adjusted accordingly.

## Startup Script Exports

`scripts/start.sh` currently exports these Ollama-related variables before startup:

```bash
export OLLAMA_BASE_URL="http://cscigpu08.bc.edu:11434"
export OLLAMA_MODEL="gpt-oss:20b"
export OLLAMA_EMBED_MODEL="qwen3-embedding:8b"
```

These matter for chatbot-related features, not for core PyTC training or inference bring-up.

## Python Runtime

- Python requirement in `pyproject.toml`: `>=3.10,<3.12`
- current bootstrap uses Python `3.11`
- `uv` installs the Python environment in `.venv`

## PyTC Dependency Acquisition

`pyproject.toml` expects an editable local path dependency:

- `pytorch_connectomics`

Fresh machines should obtain that directory using:

```bash
scripts/setup_pytorch_connectomics.sh
```

Pinned upstream source at the time of this handoff:

- repo: `https://github.com/PytorchConnectomics/pytorch_connectomics.git`
- commit: `0a0dceb`
