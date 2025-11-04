# pytc-client

## Quickstart (uv workflow)

**Prerequisites**
- [uv](https://docs.astral.sh/uv/) (bundles Python and virtualenv management)
- [Node.js](https://nodejs.org/) 18+ (includes npm)

Clone the repository and run the bootstrap script once to install everything (Python 3.11 environment, pytorch_connectomics checkout, npm packages):

```bash
./scripts/bootstrap.sh          # macOS / Linux
scripts\bootstrap.ps1           # Windows (PowerShell)
```

Launch the full stack (both FastAPI services + Electron client) with a single command:

```bash
./start.sh                      # macOS / Linux
start.bat                       # Windows (CMD)
```

The launcher keeps the API services running while Electron is open and cleans them up when you exit.
