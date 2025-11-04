# pytc-client

## Quickstart (uv workflow)

**Prerequisites**
- [git](https://git-scm.com/)
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

## Alternate Setups

- **Docker**: `docker pull xbalbinus/pytc-client:0.0.1` followed by `docker run -it -p 4242:4242 -p 4243:4243 -p 4244:4244 -p 6006:6006 --shm-size=8g xbalbinus/pytc-client:0.0.1`
- **Manual Python environment**: still supported—create/activate your own virtualenv, run `pip install -r server_api/requirements.txt`, execute `setup_pytorch_connectomics.sh`, and install the package with `pip install -e pytorch_connectomics`.

## Video Demo
[Video walkthrough](https://www.loom.com/share/45c09b36bf37408fb3e5a9172e427deb?sid=2777bf8f-a705-4d47-b17a-adf882994168)
