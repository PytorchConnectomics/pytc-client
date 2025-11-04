# pytc-client

## Recommended Setup (uv)

We strongly recommend using [uv](https://docs.astral.sh/uv/) because it bundles Python 3.11, installs dependencies in seconds, and keeps the workflow to two commands.

**Prerequisites**
- [git](https://git-scm.com/)
- [uv](https://docs.astral.sh/uv/)
- [Node.js](https://nodejs.org/) 18+ (includes npm)

### 1. Bootstrap (one-time)

```bash
./scripts/bootstrap.sh                  # macOS / Linux
scripts\bootstrap.ps1                   # Windows PowerShell
```

### 2. Launch the full stack

```bash
./start.sh                              # macOS / Linux
start.bat                               # Windows CMD
```

This starts both FastAPI services under uv, runs the Electron client, and cleans up the servers when you close the UI. Re-run the bootstrap script any time you need to refresh dependencies.

## Legacy Manual Setup (without uv)

If you prefer to manage Python environments yourself, follow the steps below. Expect a slower install and more moving pieces.

**Prerequisites**
- Python 3.9–3.11 (conda, pyenv, or system Python)
- [git](https://git-scm.com/)
- [Node.js](https://nodejs.org/) 18+ (includes npm)

1. **Create / activate an environment**
   ```bash
   python -m venv .venv
   source .venv/bin/activate        # Windows: .\.venv\Scripts\activate
   ```
2. **Install backend dependencies**
   ```bash
   pip install -r server_api/requirements.txt
   ```
3. **Download & install pytorch_connectomics**
   ```bash
   ./setup_pytorch_connectomics.sh
   pip install -e pytorch_connectomics
   ```
4. **Install frontend dependencies**
   ```bash
   cd client
   npm install
   cd ..
   ```
5. **Run the app (three terminals or background processes)**
   ```bash
   python server_api/main.py
   python server_pytc/main.py
   cd client && npm run electron
   ```

## Video Demo
[Video walkthrough](https://www.loom.com/share/45c09b36bf37408fb3e5a9172e427deb?sid=2777bf8f-a705-4d47-b17a-adf882994168)
