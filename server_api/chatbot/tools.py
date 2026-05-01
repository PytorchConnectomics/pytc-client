"""Tools for the multi-agent chatbot system.

This module provides tools for:
1. Training Agent - config selection, training command generation
2. Inference Agent - checkpoint listing, inference command generation
3. Documentation search via RAG
"""

from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime
import yaml

from langchain_core.tools import tool


def get_pytc_root() -> Path:
    """Get the pytorch_connectomics root directory."""
    return Path(__file__).parent.parent.parent / "pytorch_connectomics"


@tool
def list_training_configs() -> List[Dict[str, str]]:
    """
    List all available training configuration files with descriptions.
    Use this to help users choose the right config for their task.

    Returns:
        List of configs with name, path, model info, and description
    """
    pytc_root = get_pytc_root()
    tutorials_dir = pytc_root / "tutorials"

    if not tutorials_dir.exists():
        return [{"error": f"Tutorials directory not found at {tutorials_dir}"}]

    configs = []

    for yaml_file in tutorials_dir.rglob("*.yaml"):
        # Skip base profile files — they are not standalone configs
        if yaml_file.parent.name == "bases":
            continue

        rel_path = yaml_file.relative_to(pytc_root)
        name = yaml_file.name

        description = ""
        model_arch = "unknown"

        try:
            with open(yaml_file, "r") as f:
                config_data = yaml.safe_load(f)

            if config_data:
                # Extract model architecture from Hydra config format
                default = config_data.get("default", {})
                if isinstance(default, dict):
                    model_cfg = default.get("model", {})
                    if isinstance(model_cfg, dict):
                        arch_cfg = model_cfg.get("arch", {})
                        if isinstance(arch_cfg, dict):
                            model_arch = arch_cfg.get("profile", arch_cfg.get("type", "unknown"))

                # Read description from the YAML's own description field
                description = config_data.get("description", "")
        except Exception:
            pass

        configs.append(
            {
                "name": name,
                "path": str(rel_path),
                "full_path": str(yaml_file),
                "model": model_arch,
                "description": description or "Configuration for EM image segmentation",
            }
        )

    # Sort by name for consistency
    configs.sort(key=lambda x: x["name"])
    return configs


@tool
def read_config(config_path: str) -> Dict[str, Any]:
    """
    Read and parse a YAML configuration file to examine its settings.
    Use this to check hyperparameters, model settings, and data paths.

    Args:
        config_path: Path to YAML config (relative to pytorch_connectomics/ or absolute)

    Returns:
        Dictionary containing the full configuration
    """
    pytc_root = get_pytc_root()

    path = Path(config_path)
    if not path.is_absolute():
        path = pytc_root / config_path

    if not path.exists():
        return {"error": f"Config file not found: {path}"}

    try:
        with open(path, "r") as f:
            config = yaml.safe_load(f)
        return config
    except Exception as e:
        return {"error": f"Failed to parse config: {str(e)}"}


@tool
def list_checkpoints(experiment_name: Optional[str] = None) -> List[Dict[str, str]]:
    """
    List available trained model checkpoints.
    Use this to find models for inference or evaluation.

    Args:
        experiment_name: Optional filter by experiment name (e.g., "Lucchi_UNet")

    Returns:
        List of checkpoints with experiment name, path, and modified time
    """
    pytc_root = get_pytc_root()
    outputs_dir = pytc_root / "outputs"

    if not outputs_dir.exists():
        return [{"info": "No outputs directory found. Train a model first."}]

    checkpoints = []

    search_dirs = [outputs_dir]
    if experiment_name:
        exp_dir = outputs_dir / experiment_name
        if exp_dir.exists():
            search_dirs = [exp_dir]
        else:
            return [{"info": f"Experiment '{experiment_name}' not found in outputs/"}]

    # Search for .ckpt (Lightning) and .pth files
    for search_dir in search_dirs:
        for pattern in ["*.ckpt", "*.pth"]:
            for ckpt_file in search_dir.rglob(pattern):
                rel_path = ckpt_file.relative_to(pytc_root)

                # Determine experiment name from path
                parts = rel_path.parts
                exp_name = parts[1] if len(parts) > 1 else "unknown"

                checkpoints.append(
                    {
                        "experiment_name": exp_name,
                        "checkpoint_name": ckpt_file.name,
                        "path": str(rel_path),
                        "full_path": str(ckpt_file),
                        "modified_time": datetime.fromtimestamp(
                            ckpt_file.stat().st_mtime
                        ).strftime("%Y-%m-%d %H:%M:%S"),
                    }
                )

    if not checkpoints:
        return [{"info": "No checkpoints found. Train a model first."}]

    # Sort by modified time (newest first)
    checkpoints.sort(key=lambda x: x.get("modified_time", ""), reverse=True)
    return checkpoints


@tool
def search_documentation(query: str) -> str:
    """
    Search PyTC documentation for guides, UI explanations, and feature descriptions.
    Use this for questions about how to use the application or what features do.

    Args:
        query: The user's question or search query

    Returns:
        Relevant documentation content
    """
    # Placeholder - actual retriever is injected at runtime in chatbot.py
    pass


TRAINING_TOOLS = [
    list_training_configs,
    read_config,
]

INFERENCE_TOOLS = [
    list_checkpoints,
    read_config,
]

ALL_TOOLS = [
    list_training_configs,
    read_config,
    list_checkpoints,
    search_documentation,
]
