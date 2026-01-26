### High-level structure

- **`client`** - Electron + React frontend (CRA)
  - `client/main.js` - Electron entrypoint
  - `client/src` - React UI code
- **`server_api`** - FastAPI backend server
  - `server_api/main.py` — API entrypoint
- **`server_pytc`** - PyTC worker service used for model inference or background tasks
  - `server_pytc/main.py` — worker entrypoint
- **`pytorch_connectomics`** - PyTC library containing models, configs, and utilities used by the PyTC worker
  - `pytorch_connectomics/setup.py` — library installation
  - `pytorch_connectomics/configs` — example YAML model config files
- **`scripts`** - for installation and set-up
