# Development Environment Migration Guide (Linux Edition)

This guide details the steps to set up the `pytc-client` development environment on a fresh **Linux** machine, targeting the `mito-mvp` branch. This branch contains the latest Hydra-based inference integration and critical fixes for legacy checkpoint compatibility.

## 1. Session Context & Status

### 1.1 Objective
The primary goal of the recent development session was to enable **Hydra-based inference** using the `monai_unet` architecture on the `v2.0` branch of `pytorch_connectomics`, while maintaining compatibility with a **legacy model checkpoint**.

### 1.2 Work Completed
We have successfully:
1.  **Codebase Migration**: Switched the `pytorch_connectomics` submodule to the `v2.0` branch to support Hydra configuration.
2.  **Config Schema Fixes**: Updated `client/src/contexts/GlobalContext.js` to match the new Hydra schema:
    *   Removed invalid keys: `upsample`, `preset`, `affine`, `rotate.spatial_axes`.
    *   Fixed `postprocessing` keys: `intensity_scale` -> `output_scale`.
3.  **API Logic Update**: Refactored `client/src/utils/api.js` to correctly inject the `output_path` into `inference.data.output_path` (instead of the root `inference` object).
4.  **Legacy Checkpoint Support**:
    *   **Dummy Classes**: Injected dummy configuration classes (`DataTransformConfig`, `EdgeModeConfig`, `AffineConfig`, `StripeConfig`) into `connectomics/config/hydra_config.py` to resolve `AttributeError`s during unpickling.
    *   **PyTorch Compatibility**: Monkeypatched `torch.load` in `scripts/main.py` to force `weights_only=False`, resolving security restrictions in newer PyTorch versions.
5.  **Data Handling**: Excluded large data files (`lucchi_test`, `test_output`) from the repository to maintain a lightweight history. **Manual transfer is required.**

### 1.3 Next Steps
On the new machine, the immediate goal is to:
1.  Clone this repository (`mito-mvp` branch).
2.  Install dependencies.
3.  Run the inference workflow to verify reproducibility.
4.  Continue development on the `monai_unet` integration.

---

## 2. Prerequisites (Linux)

Ensure the following are installed on the target Linux machine (Ubuntu/Debian assumed):

```bash
# System updates
sudo apt-get update && sudo apt-get upgrade -y

# Python 3.11
sudo apt-get install -y python3.11 python3.11-venv python3.11-dev build-essential

# Git
sudo apt-get install -y git

# Node.js (v16+)
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
sudo apt-get install -y nodejs
```

**GPU Support (Optional but Recommended)**:
If the machine has an NVIDIA GPU, ensure CUDA drivers (11.8 or 12.x) are installed. The `pytorch` installation step below will need to match your CUDA version.

## 3. Repository Setup

Clone the repository and switch to the correct branch.

```bash
# Clone the repository
git clone <repository-url> pytc-client
cd pytc-client

# Checkout the migration branch
git checkout mito-mvp

# Initialize and update the submodule
git submodule update --init --recursive
```

**Critical Step**: Ensure the `pytorch_connectomics` submodule is synced.
```bash
cd pytorch_connectomics
# The main repo points to a specific commit on the v2.0 branch
git checkout v2.0
cd ..
```

## 4. Backend Setup

Set up the Python environment.

### 4.1 Create Virtual Environment
```bash
# Create venv
python3.11 -m venv .venv
source .venv/bin/activate
```

### 4.2 Install Dependencies
```bash
# Upgrade pip
pip install --upgrade pip

# Install core dependencies
# NOTE: If using GPU, check pytorch.org for the specific command, e.g.:
# pip install torch torchvision --index-url https://download.pytorch.org/whl/cu118
pip install -r requirements.txt

# Install pytorch_connectomics in editable mode (CRITICAL)
cd pytorch_connectomics
pip install -e .
cd ..

# Verify installation
python -c "import connectomics; print(connectomics.__file__)"
```

## 5. Frontend Setup

```bash
cd client
npm install
cd ..
```

## 6. Data Setup (Manual Transfer Required)

**Important**: The `lucchi_test` dataset contains large files that are **not** included in the git repository. You must transfer them manually.

### 6.1 Transfer Data
Copy the `lucchi_test` directory from the original development machine to the root of the `pytc-client` directory on the new machine.

### 6.2 Verify Files
Ensure the following files are present in `lucchi_test/` after transfer:
- `lucchiIm.tif`
- `lucchiLabels.tif`
- `epoch=269-step=5400.ckpt`

## 7. Running the Application

Use the provided start script.

```bash
chmod +x start.sh
./start.sh
```

### Troubleshooting
- **"Address already in use"**: Kill lingering processes on ports 4242, 4243, 3000.
  ```bash
  lsof -ti:4242,4243,3000 | xargs kill -9
  ```
- **Electron Issues on Headless Linux**: If you are running on a headless server (no display), Electron will fail to launch. You may need to run the React app in a browser (`http://localhost:3000`) and forward the ports via SSH.
  ```bash
  # SSH Tunnel example
  ssh -L 3000:localhost:3000 -L 4242:localhost:4242 -L 4243:localhost:4243 user@remote-machine
  ```

## 8. Verification

1.  Open the app (or browser at `localhost:3000`).
2.  Click **"Segment"**.
3.  Watch the terminal for "Inference process started".
4.  Check `test_output/inference/result.h5` for output.
