"""Natural-language request -> draft task script.

The LLM never writes script text. It fills a JSON form (Ollama structured
output), and `language.render` prints the script. If Ollama is unavailable or
returns something unusable, a keyword-based drafter takes over, so the editor
always gets a draft to correct.
"""

from __future__ import annotations

import json
import os
import re
import time
from typing import Any, Optional

import requests

from .compiler import PRESETS
from .language import SCHEMA, TARGETS, VERBS, render

OLLAMA_URL = os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/")
DRAFT_MODEL = os.environ.get("PYTC_DSL_DRAFT_MODEL", "gpt-oss:latest")
DRAFT_TIMEOUT = float(os.environ.get("PYTC_DSL_DRAFT_TIMEOUT", "90"))

_PATH_RE = re.compile(r"(?:\"|')?((?:/|~/)[^\s\"'<>,;]+)")

FORM_SCHEMA = {
    "type": "object",
    "properties": {
        "verb": {"type": "string", "enum": list(VERBS)},
        "target": {"type": "string", "enum": list(TARGETS)},
        "image": {"type": "string"},
        "label": {"type": "string"},
        "model": {"type": "string"},
        "prediction": {"type": "string"},
        "truth": {"type": "string"},
        "baseline": {"type": "string"},
        "output": {"type": "string"},
        "preset": {"type": "string", "enum": list(PRESETS)},
        "steps": {"type": "integer"},
        "threshold": {"type": "number"},
        "note": {"type": "string"},
    },
    "required": ["verb", "target", "note"],
}


def _paths_in(text: str) -> list[str]:
    return [p.rstrip(".?!)") for p in _PATH_RE.findall(text)]


def gather_context(request: str, target, history: list[dict[str, Any]]) -> dict[str, Any]:
    """Facts the drafter may use: files inside folders the user mentioned, and recent outputs."""
    listings: dict[str, list[str]] = {}
    for path in _paths_in(request)[:3]:
        if re.search(r"\.(h5|hdf5|tif|tiff|tar|pth|yaml)$", path):
            continue
        try:
            files = target.list_files(path)
        except Exception:  # noqa: BLE001 - context is best effort
            files = []
        if files:
            listings[path] = files
    recent = [
        {"request": h.get("request", ""), "verb": h.get("verb"), "state": h.get("state"), "outputs": h.get("outputs", {})}
        for h in history[-5:]
    ]
    files_named = [p for p in _paths_in(request) if re.search(r"\.(h5|hdf5|tif|tiff|tar|pth)$", p)]
    return {"files_named_in_request": files_named, "folders": listings, "recent_runs": recent}


def _system_prompt(target_name: str, output_root: str) -> str:
    fields = {verb: [f"{s.name} ({s.help}{', required' if s.required else ''})" for s in specs] for verb, specs in SCHEMA.items()}
    return (
        "You turn a biologist's request into a form for a segmentation workflow tool.\n"
        f"Task kinds and their fields: {json.dumps(fields)}\n"
        f"Presets: {', '.join(PRESETS)}. Use synthetic-tiny unless the user names another.\n"
        f"Default target: {target_name}.\n"
        "Rules:\n"
        "- Only use file paths that appear in files_named_in_request, the folder listings, or recent run outputs. Never invent paths.\n"
        "- A file the user names in the request is almost always the image (or the file to score/view).\n"
        "- For training, pick an image file and its matching label/segmentation/ground-truth file from the listings.\n"
        "- 'my model' or 'the model I just trained' means the newest checkpoint in recent run outputs.\n"
        f"- If no output folder is given, use {output_root}/<kind>-<short-name>.\n"
        "- Leave a field empty if you cannot fill it from the facts. The user will fill it in.\n"
        "- note: one short sentence telling the user what you assumed."
    )


def _ask_llm(request: str, context: dict[str, Any], target_name: str, output_root: str) -> Optional[dict[str, Any]]:
    body = {
        "model": DRAFT_MODEL,
        "stream": False,
        "format": FORM_SCHEMA,
        "think": "low",
        "options": {"temperature": 0},
        "messages": [
            {"role": "system", "content": _system_prompt(target_name, output_root)},
            {"role": "user", "content": f"Facts: {json.dumps(context)}\n\nRequest: {request}"},
        ],
    }
    response = requests.post(f"{OLLAMA_URL}/api/chat", json=body, timeout=DRAFT_TIMEOUT)
    response.raise_for_status()
    content = response.json().get("message", {}).get("content", "")
    form = json.loads(content)
    return form if isinstance(form, dict) and form.get("verb") in VERBS else None


def _pick(files: list[str], *words: str, avoid: tuple[str, ...] = ()) -> str:
    for file in files:
        name = file.lower().rsplit("/", 1)[-1]
        if any(w in name for w in words) and not any(a in name for a in avoid):
            return file
    return ""


def _rules(request: str, context: dict[str, Any], target_name: str, output_root: str) -> dict[str, Any]:
    text = request.lower()
    if re.search(r"\b(evaluat|score|dice|accura|compare)", text):
        verb = "evaluate"
    elif re.search(r"\b(view|show|visuali[sz]e|open|look at)", text):
        verb = "view"
    elif re.search(r"\b(infer|inference|predict|segment|run .*model|apply)", text):
        verb = "infer"
    else:
        verb = "train"
    files = [f for listing in context["folders"].values() for f in listing] + [
        p for p in context.get("files_named_in_request", [])
    ]
    checkpoints = [r["outputs"].get("checkpoint") for r in context["recent_runs"] if r["outputs"].get("checkpoint")]
    predictions = [r["outputs"].get("prediction") for r in context["recent_runs"] if r["outputs"].get("prediction")]
    form: dict[str, Any] = {"verb": verb, "target": target_name, "note": "Drafted by keyword rules, so please check every field."}
    stamp = time.strftime("%m%d-%H%M")
    if verb == "train":
        form.update(image=_pick(files, "train", "image", "_im", "raw", avoid=("seg", "label", "truth")) or _pick(files, "image", "_im", "raw"),
                    label=_pick(files, "ground_truth", "label", "seg", "truth"),
                    preset="synthetic-tiny", steps=200, output=f"{output_root}/train-{stamp}")
    elif verb == "infer":
        model = _pick(files, ".pth") or (checkpoints[-1] if checkpoints else "")
        form.update(model=model, image=_pick(files, "target", "test", "image", "_im", avoid=("seg", "label", "truth")),
                    preset="synthetic-tiny", output=f"{output_root}/infer-{stamp}")
    elif verb == "evaluate":
        form.update(prediction=(predictions[-1] if predictions else _pick(files, "pred", "candidate")),
                    truth=_pick(files, "ground_truth", "truth", "label", "seg"), threshold=0.5)
    else:
        form.update(image=_pick(files, "image", "_im", "raw"),
                    label=_pick(files, "pred", "seg", "label") or (predictions[-1] if predictions else ""))
    return form


def _apply_code_defaults(verb: str, fields: dict[str, Any], request: str, target_name: str, output_root: str) -> dict[str, Any]:
    """Settings the user did not state come from code, not from the model."""
    numbers_in_request = re.findall(r"\b\d+(?:\.\d+)?\b", re.sub(_PATH_RE, " ", request))
    for spec in SCHEMA[verb]:
        if spec.kind in ("int", "float") and spec.name in fields and not numbers_in_request:
            fields[spec.name] = spec.default
        if spec.kind == "preset" and spec.name in fields and spec.name not in request.lower() and str(fields[spec.name]) not in request:
            fields[spec.name] = spec.default
    if "output" in {s.name for s in SCHEMA[verb]} and not str(fields.get("output", "")).startswith("/"):
        fields["output"] = f"{output_root}/{verb}-{time.strftime('%m%d-%H%M%S')}"
    return fields


def draft(request: str, target, history: list[dict[str, Any]], output_root: str) -> dict[str, Any]:
    context = gather_context(request, target, history)
    source, error, form = "llm", "", None
    started = time.time()
    try:
        form = _ask_llm(request, context, target.name, output_root)
    except Exception as exc:  # noqa: BLE001 - fall back to rules on any LLM problem
        error = str(exc)[:200]
    if not form:
        source = "rules"
        form = _rules(request, context, target.name, output_root)
    verb = form["verb"]
    allowed = {s.name for s in SCHEMA[verb]}
    fields = {k: v for k, v in form.items() if k in allowed and v not in (None, "")}
    if source == "llm":  # backstop: fill fields the model left empty from the keyword rules
        backup = _rules(request, context, target.name, output_root)
        if backup["verb"] == verb:
            for key, value in backup.items():
                if key in allowed and key not in fields and value not in (None, ""):
                    fields[key] = value
    fields = _apply_code_defaults(verb, fields, request, form.get("target") or target.name, output_root)
    note = form.get("note", "")
    script = render({"verb": verb, "target": form.get("target") or target.name, "fields": fields},
                    comment=f'Drafted from: "{request.strip()[:100]}"')
    return {
        "script": script,
        "source": source,
        "model": DRAFT_MODEL if source == "llm" else None,
        "note": note,
        "llm_error": error,
        "seconds": round(time.time() - started, 1),
        "context": context,
    }
