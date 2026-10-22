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
from .language import SCHEMA, TARGETS, VERBS, format_value, render

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
        "options": {"temperature": 0, "num_ctx": 8192},
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



CLASSIFY_SCHEMA = {
    "type": "object",
    "properties": {
        "kind": {"type": "string", "enum": ["answer", "revise"]},
        "reply": {"type": "string"},
        "line": {"type": "integer"},
    },
    "required": ["kind", "reply"],
}
REVISE_SCHEMA = {
    "type": "object",
    "properties": {**{k: v for k, v in FORM_SCHEMA["properties"].items() if k != "note"},
                   "set_lines": {"type": "string"}},
    "required": ["verb", "target", "set_lines"],
}


def _json_from(text: str) -> dict[str, Any]:
    """Structured output, with a fallback for models that wrap JSON in prose."""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.S)
        if match:
            return json.loads(match.group(0))
        raise


def _clean_reply(text: str) -> str:
    text = re.sub(r"\s*[{}]+\s*(Done\.?)?\s*[{}]*\s*$", "", text.strip())
    return text.replace("\u2011", "-").strip()


class UnstructuredReply(ValueError):
    """The model answered in prose instead of the requested JSON."""

    def __init__(self, content: str, thinking: str) -> None:
        super().__init__("The model did not return the requested form.")
        self.content, self.thinking = content, thinking


def _chat(messages: list[dict[str, str]], schema: dict[str, Any]) -> dict[str, Any]:
    body = {"model": DRAFT_MODEL, "stream": False, "format": schema, "think": "low",
            "options": {"temperature": 0, "num_ctx": 8192}, "messages": messages}
    content = thinking = ""
    for attempt in range(2):
        if attempt:  # gpt-oss sometimes ignores the format; ask again, more firmly
            body["messages"] = messages + [{"role": "user", "content": "Reply with only the JSON object, nothing else."}]
        response = requests.post(f"{OLLAMA_URL}/api/chat", json=body, timeout=DRAFT_TIMEOUT)
        response.raise_for_status()
        message = response.json().get("message", {})
        content, thinking = message.get("content", ""), message.get("thinking", "")
        try:
            return _json_from(content)
        except json.JSONDecodeError:
            continue
    raise UnstructuredReply(content, thinking)


def _facts_block(context: dict[str, Any], request: str, draft_note: str, script_text: str) -> str:
    numbered = "\n".join(f"{i:>2} | {line}" for i, line in enumerate(script_text.splitlines(), start=1))
    return (f"Facts: {json.dumps(context)}\nOriginal request: {request}\nNote from the draft: {draft_note}\n"
            "How the draft was made: files were picked from the folder listings and recent runs; steps defaults to "
            "100 and preset to synthetic-tiny unless the user said otherwise; the output folder name is generated "
            "by code from the date and time.\n"
            f"Current script (line numbers on the left):\n{numbered}")


def converse(request: str, script_text: str, message: str, thread: list[dict[str, str]],
             task: dict[str, Any] | None, target, history: list[dict[str, Any]], draft_note: str = "") -> dict[str, Any]:
    started = time.time()
    inputs = {k: v for k, v in (task or {}).get("fields", {}).items() if k not in ("output",)}
    folder_hint = request + " " + " ".join(
        str(v).rsplit("/", 1)[0] for v in inputs.values() if isinstance(v, str) and v.startswith("/")
    )
    context = gather_context(folder_hint, target, history)
    facts = _facts_block(context, request, draft_note, script_text)
    earlier = "\n".join(f"{t.get('role')}: {t.get('text')}" for t in thread[-6:])
    try:
        decided = _chat([
            {"role": "system", "content": (
                "You review a task script with a biologist before it runs. Decide what their message wants.\n"
                "kind=answer: a question. reply explains in 1-3 plain sentences, using only the facts. If it is about "
                "one script line, set `line` to that line number.\n"
                "kind=revise: feedback or a requested change. reply says in one sentence what you will change.")},
            {"role": "user", "content": f"{facts}\n\nEarlier conversation:\n{earlier or '(none)'}\n\nMessage: {message}"},
        ], CLASSIFY_SCHEMA)
    except UnstructuredReply as exc:
        # Read the prose instead: the model's reasoning usually names the kind; a question mark settles the rest.
        said = (exc.thinking + " " + exc.content).lower()
        is_question = message.strip().endswith("?") or re.match(r"^(why|what|how|which|where|when|who|is|are|does|did|can)\b", message.strip().lower())
        kind = "revise" if "revise" in said else "answer" if "answer" in said else ("answer" if is_question else "revise")
        decided = {"kind": kind, "reply": exc.content.strip() or "Working on it."}
    except Exception as exc:  # noqa: BLE001
        return {"kind": "error", "reply": f"Could not reach the drafting model ({str(exc)[:120]}). "
                                          "You can still edit the script directly.", "seconds": round(time.time() - started, 1)}
    result: dict[str, Any] = {"kind": decided.get("kind", "answer"), "reply": _clean_reply(decided.get("reply", "")),
                              "line": decided.get("line"), "seconds": 0}
    if result["kind"] == "revise":
        fields_now = (task or {}).get("fields", {})
        sets_now = "\n".join(f"{s['key']} {format_value(s['value'])}" for s in (task or {}).get("sets", []))
        try:
            form = _chat([
                {"role": "system", "content": (
                    "Rewrite a task form to apply the user's change. Start from the current values and change only "
                    "what the user asked for. Keep every other value exactly.\n"
                    f"Task kinds and fields: {json.dumps({v: [s.name for s in specs] for v, specs in SCHEMA.items()})}\n"
                    "set_lines: one `KEY VALUE` per line for YAML config changes, e.g. `SOLVER.BASE_LR 0.001`. "
                    "Learning rate is SOLVER.BASE_LR, batch size is SOLVER.SAMPLES_PER_BATCH. Use '' for none.\n"
                    "Never invent file paths: only use paths from the current values or the folder listings.")},
                {"role": "user", "content": (
                    f"Facts: {json.dumps(context)}\nCurrent values: verb={(task or {}).get('verb')}, "
                    f"target={(task or {}).get('target')}, fields={json.dumps(fields_now)}\n"
                    f"Current set_lines:\n{sets_now or '(none)'}\n\nChange requested: {message}")},
            ], REVISE_SCHEMA)
        except Exception:  # noqa: BLE001
            result.update(kind="error", reply="The model described a change but did not write it as a script. "
                                              "Try rephrasing, or edit the line yourself.")
            form = None
        if form:
            import yaml

            verb = form.get("verb") or (task or {}).get("verb") or "train"
            allowed = {s.name for s in SCHEMA.get(verb, ())}
            # Start from the current script so nothing the model omits gets lost.
            fields = dict(fields_now) if verb == (task or {}).get("verb") else {}
            fields.update({k: v for k, v in form.items() if k in allowed and v not in (None, "")})
            removing = re.search(r"\b(remove|delete|drop|undo|get rid|without)\b", message.lower())
            sets_by_key = {} if removing else {s["key"]: s["value"] for s in (task or {}).get("sets", [])}
            for line in str(form.get("set_lines") or "").splitlines():
                parts = line.strip().removeprefix("set ").split(None, 1)
                if len(parts) != 2:
                    continue
                key, raw = parts[0], parts[1].strip().strip('"')
                try:
                    value = yaml.safe_load(raw)
                except Exception:  # noqa: BLE001
                    value = raw
                if key in allowed:  # the model put a script field here; treat it as a field change
                    fields[key] = raw if isinstance(value, str) else value
                elif "." in key:
                    sets_by_key[key] = value
            sets = [{"key": k, "value": v} for k, v in sets_by_key.items()]
            first = script_text.splitlines()[0] if script_text.strip() else ""
            comment = first[2:] if first.startswith("# ") else ""
            result["script"] = render({"verb": verb, "target": form.get("target") or (task or {}).get("target"),
                                       "fields": fields, "sets": sets}, comment=comment)
            result["reply"] = _describe_change(task or {}, fields, sets) or "No changes were needed."
    result["seconds"] = round(time.time() - started, 1)
    return result


def _short(value: Any) -> str:
    text = format_value(value) if not isinstance(value, str) else value
    return text.rsplit("/", 1)[-1] if isinstance(value, str) and value.startswith("/") else text


def _describe_change(old: dict[str, Any], fields: dict[str, Any], sets: list[dict[str, Any]]) -> str:
    """The reply for a revision is written from the actual diff, so it can't disagree with the script."""
    parts = []
    before = old.get("fields", {})
    for key, value in fields.items():
        if key in before and before[key] != value:
            parts.append(f"{key} {_short(before[key])} → {_short(value)}")
        elif key not in before:
            parts.append(f"added {key} {_short(value)}")
    for key in before:
        if key not in fields:
            parts.append(f"removed {key}")
    old_sets = {s["key"]: s["value"] for s in old.get("sets", [])}
    new_sets = {s["key"]: s["value"] for s in sets}
    for key, value in new_sets.items():
        if key not in old_sets:
            parts.append(f"added set {key} {format_value(value)}")
        elif old_sets[key] != value:
            parts.append(f"set {key} {format_value(old_sets[key])} → {format_value(value)}")
    for key in old_sets:
        if key not in new_sets:
            parts.append(f"removed set {key}")
    return ("Proposed: " + "; ".join(parts) + ".") if parts else ""
