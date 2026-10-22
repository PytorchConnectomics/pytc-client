"""Deterministic compiler: checked task script -> exact config, command, and change list.

No LLM is involved here. The same script always compiles to the same plan.
"""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .language import TaskScript

REPO_ROOT = Path(__file__).resolve().parents[2]
PRESETS: dict[str, Path] = {
    "synthetic-tiny": Path(__file__).with_name("presets") / "synthetic-tiny.yaml",
    "mito25-smoke": REPO_ROOT / "pytorch_connectomics/configs/MitoEM/Mito25-Local-Smoke-BC.yaml",
    "lucchi-mito": REPO_ROOT / "pytorch_connectomics/configs/Lucchi-Mitochondria.yaml",
}
PREDICTION_NAME = "prediction.h5"
_VALID_AUG_NUMS = (None, 0, 4, 8, 16)


@dataclass
class Plan:
    verb: str
    target: str
    files: dict[str, str] = field(default_factory=dict)  # job-dir filename -> text
    command: str = ""  # run from the job dir; {python} and {pytc} are filled in by the target
    changes: list[dict[str, Any]] = field(default_factory=list)
    outputs: dict[str, str] = field(default_factory=dict)
    needs_gpu: bool = False
    summary: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "verb": self.verb,
            "target": self.target,
            "files": self.files,
            "command": self.command,
            "changes": self.changes,
            "outputs": self.outputs,
            "needs_gpu": self.needs_gpu,
            "summary": self.summary,
        }


def _get(cfg: dict, key: str) -> Any:
    node: Any = cfg
    for part in key.split("."):
        if not isinstance(node, dict) or part not in node:
            return None
        node = node[part]
    return node


def _set(cfg: dict, key: str, value: Any, changes: list, source: str, why: str) -> None:
    parts = key.split(".")
    node = cfg
    for part in parts[:-1]:
        node = node.setdefault(part, {})
    old = node.get(parts[-1])
    if old == value:
        return
    node[parts[-1]] = value
    changes.append({"key": key, "old": old, "new": value, "source": source, "why": why})


def load_preset(name: str) -> dict:
    return yaml.safe_load(PRESETS[name].read_text()) or {}


def _lint(cfg: dict, changes: list) -> None:
    """Automatic fixes for config combinations PyTorch Connectomics rejects at run time."""
    filters = _get(cfg, "MODEL.FILTERS")
    if _get(cfg, "MODEL.NORM_MODE") == "gn" and isinstance(filters, list) and any(f % 8 for f in filters):
        fixed = [f if f % 8 == 0 else (f // 8 + 1) * 8 for f in filters]
        _set(cfg, "MODEL.FILTERS", fixed, changes, "auto-fix",
             "Group norm needs channel counts that are multiples of 8, or the model fails to build.")
    if _get(cfg, "INFERENCE.AUG_NUM") not in _VALID_AUG_NUMS:
        _set(cfg, "INFERENCE.AUG_NUM", 0, changes, "auto-fix",
             "Test-time augmentation only accepts 4, 8, or 16 copies; 0 turns it off.")
    total = _get(cfg, "SOLVER.ITERATION_TOTAL")
    warmup = _get(cfg, "SOLVER.WARMUP_ITERS")
    if isinstance(total, int) and isinstance(warmup, int) and warmup >= total:
        _set(cfg, "SOLVER.WARMUP_ITERS", max(1, total // 5), changes, "auto-fix",
             "Warm-up must be shorter than the whole training run.")


def _dump(cfg: dict) -> str:
    return yaml.safe_dump(cfg, sort_keys=False, default_flow_style=None, allow_unicode=False)


def compile_script(script: TaskScript) -> Plan:
    verb, target = script.verb, script.target
    plan = Plan(verb=verb, target=target)
    gpus = 1 if target == "cluster" else 0

    if verb in ("train", "infer"):
        preset = script.get("preset")
        cfg = copy.deepcopy(load_preset(preset))
        changes: list[dict[str, Any]] = []
        _set(cfg, "SYSTEM.NUM_GPUS", gpus, changes, "target",
             "One GPU on the cluster." if gpus else "CPU only on the laptop.")
        _set(cfg, "DATASET.INPUT_PATH", "", changes, "script", "Paths below are absolute.")
        if verb == "train":
            steps = int(script.get("steps"))
            out = script.get("output")
            _set(cfg, "DATASET.IMAGE_NAME", script.get("image"), changes, "script", "`image` in your script.")
            _set(cfg, "DATASET.LABEL_NAME", script.get("label"), changes, "script", "`label` in your script.")
            _set(cfg, "DATASET.OUTPUT_PATH", out, changes, "script", "`output` in your script.")
            _set(cfg, "SOLVER.ITERATION_TOTAL", steps, changes, "script", "`steps` in your script.")
            _set(cfg, "SOLVER.ITERATION_SAVE", steps, changes, "script", "Save one checkpoint at the end.")
            _set(cfg, "SOLVER.ITERATION_VAL", steps * 10, changes, "script", "No validation passes in a short run.")
            for item in script.sets:
                _set(cfg, item.key, item.value, changes, "script", f"`set` on line {item.line} of your script.")
            _lint(cfg, changes)
            plan.command = "{python} {pytc}/scripts/main.py --config-file config.yaml"
            plan.outputs = {"checkpoint": f"{out.rstrip('/')}/checkpoint_{steps:05d}.pth.tar", "folder": out}
            plan.summary = f"Train the {preset} model for {steps} steps on {script.get('image').rsplit('/', 1)[-1]}"
        else:
            out = script.get("output")
            _set(cfg, "INFERENCE.IMAGE_NAME", script.get("image"), changes, "script", "`image` in your script.")
            _set(cfg, "INFERENCE.INPUT_PATH", "", changes, "script", "Paths below are absolute.")
            _set(cfg, "INFERENCE.OUTPUT_PATH", out, changes, "script", "`output` in your script.")
            _set(cfg, "INFERENCE.OUTPUT_NAME", PREDICTION_NAME, changes, "script", "Fixed name so later steps can find it.")
            for item in script.sets:
                _set(cfg, item.key, item.value, changes, "script", f"`set` on line {item.line} of your script.")
            _lint(cfg, changes)
            model = script.get("model")
            plan.command = f"{{python}} {{pytc}}/scripts/main.py --config-file config.yaml --inference --checkpoint '{model}'"
            plan.outputs = {"prediction": f"{out.rstrip('/')}/{PREDICTION_NAME}", "folder": out}
            plan.summary = f"Segment {script.get('image').rsplit('/', 1)[-1]} with {model.rsplit('/', 1)[-1]}"
        plan.files["config.yaml"] = _dump(cfg)
        plan.changes = changes
        plan.needs_gpu = bool(gpus)
    elif verb == "evaluate":
        params = {
            "prediction": script.get("prediction"),
            "truth": script.get("truth"),
            "baseline": script.get("baseline"),
            "threshold": script.get("threshold"),
        }
        plan.files["params.json"] = json.dumps(params, indent=2)
        plan.files["evaluate.py"] = EVALUATE_PY
        plan.command = "{python} evaluate.py params.json"
        plan.outputs = {"metrics": "metrics.json"}
        plan.summary = f"Score {params['prediction'].rsplit('/', 1)[-1]} against {params['truth'].rsplit('/', 1)[-1]}"
    elif verb == "view":
        plan.outputs = {"image": script.get("image")}
        if script.get("label"):
            plan.outputs["label"] = script.get("label")
        plan.summary = "Open in Neuroglancer" + (" (files are copied from the cluster first)" if target == "cluster" else "")
    return plan


EVALUATE_PY = r'''"""Foreground Dice and IoU for a prediction against ground truth. Written by the task-script compiler."""
import json, sys
import numpy as np


def load(path):
    if path.endswith((".h5", ".hdf5")):
        import h5py
        with h5py.File(path, "r") as f:
            key = "main" if "main" in f else list(f.keys())[0]
            return np.asarray(f[key])
    import tifffile
    return tifffile.imread(path)


def foreground(pred, threshold):
    pred = np.asarray(pred)
    if pred.ndim == 4:
        pred = pred[0]  # first channel is foreground probability
    pred = pred.astype(np.float32)
    if pred.max() > 1.0:
        pred = pred / 255.0
    return pred >= threshold


def score(pred_path, truth, threshold):
    pred = foreground(load(pred_path), threshold)
    if pred.shape != truth.shape:
        raise SystemExit(f"Shape mismatch: prediction {pred.shape} vs truth {truth.shape}")
    inter = np.logical_and(pred, truth).sum()
    dice = 2 * inter / max(1, pred.sum() + truth.sum())
    iou = inter / max(1, np.logical_or(pred, truth).sum())
    return {"dice": round(float(dice), 4), "iou": round(float(iou), 4)}


params = json.load(open(sys.argv[1]))
truth = load(params["truth"]) > 0
result = {"prediction": score(params["prediction"], truth, params["threshold"])}
if params.get("baseline"):
    result["baseline"] = score(params["baseline"], truth, params["threshold"])
    result["dice_change"] = round(result["prediction"]["dice"] - result["baseline"]["dice"], 4)
json.dump(result, open("metrics.json", "w"), indent=2)
print("METRICS " + json.dumps(result))
'''
