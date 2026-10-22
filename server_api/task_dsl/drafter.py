"""Natural-language request -> draft task script.

The LLM never writes script text. It fills a JSON form (Ollama structured
output), and `language.render` prints the script. If Ollama is unavailable or
returns something unusable, a keyword-based drafter takes over, so the editor
always gets a draft to correct.
"""

from __future__ import annotations

import difflib
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



# ---------- Conversation: an editing agent with tools, like a coding assistant ----------
#
# The model never rewrites the script as text. It calls tools that edit a working copy
# (set a field, set or remove a config key) or look things up (list a folder, find config
# keys). After it stops, the checker runs on the working copy and any errors go back to
# the model once so it can repair its own edit. The user then sees the result as a diff.

MAX_TOOL_ROUNDS = 8
_PROMISE_RE = re.compile(r"\b(i'll|i will|i've|i have|let me|sure)\b.*\b(change|edit|update|set|modify|switch|replace|reduce|increase|lower|raise|add|remove)",
                         re.I | re.S)
_LINE_RE = re.compile(r"\bline\s+(\d+)\b", re.I)


def _clean_reply(text: str) -> str:
    text = re.sub(r"\s*[{}]+\s*(Done\.?)?\s*[{}]*\s*$", "", (text or "").strip())
    return text.replace("‑", "-").strip()


def _tool_specs(verb: str) -> list[dict[str, Any]]:
    field_names = [s.name for s in SCHEMA.get(verb, ())] + ["target"]
    fn = lambda name, desc, props, req: {"type": "function", "function": {  # noqa: E731
        "name": name, "description": desc,
        "parameters": {"type": "object", "properties": props, "required": req}}}
    return [
        fn("set_field", "Change one line of the task script (a named field such as steps, image, output, or target).",
           {"name": {"type": "string", "enum": field_names}, "value": {"type": "string"}}, ["name", "value"]),
        fn("set_config", "Add or change a `set KEY VALUE` line that overrides one key of the preset's YAML config, "
                         "e.g. SOLVER.BASE_LR 0.001. Use find_config_keys first if unsure of the key name.",
           {"key": {"type": "string"}, "value": {"type": "string"}}, ["key", "value"]),
        fn("remove_config", "Remove a `set` line from the script.", {"key": {"type": "string"}}, ["key"]),
        fn("find_config_keys", "Search the preset's YAML config for keys by words, e.g. 'batch' or 'learning rate'. "
                               "Returns matching keys with their current values.",
           {"query": {"type": "string"}}, ["query"]),
        fn("list_files", "List data and checkpoint files under a folder on the machine where the task runs.",
           {"folder": {"type": "string"}}, ["folder"]),
    ]


_ALIASES = {"learning rate": "BASE_LR", "lr": "BASE_LR", "batch": "SAMPLES_PER_BATCH", "iterations": "ITERATION",
            "epochs": "ITERATION", "gpus": "NUM_GPUS", "patch": "INPUT_SIZE", "channels": "FILTERS"}


class _Workspace:
    """A working copy of the task the agent edits through tools."""

    def __init__(self, task: dict[str, Any], target) -> None:
        self.verb = task.get("verb") or "train"
        self.target_name = task.get("target") or target.name
        self.fields = dict(task.get("fields", {}))
        self.sets = {s["key"]: s["value"] for s in task.get("sets", [])}
        self.target = target
        self.edits = 0

    def _flat_config(self) -> dict[str, Any]:
        import yaml

        from .compiler import PRESETS as _P
        from .language import _flatten

        preset = self.fields.get("preset") or "synthetic-tiny"
        if preset not in _P:
            return {}
        return _flatten(yaml.safe_load(_P[preset].read_text()) or {})

    def run(self, name: str, args: dict[str, Any]) -> str:
        import yaml

        from .language import MANAGED_KEYS

        if name == "set_field":
            field, value = str(args.get("name", "")), str(args.get("value", "")).strip().strip('"')
            if field == "target":
                if value not in TARGETS:
                    return f"Error: target must be one of {', '.join(TARGETS)}."
                self.target_name = value
            else:
                spec = next((s for s in SCHEMA.get(self.verb, ()) if s.name == field), None)
                if spec is None:
                    return f"Error: `{field}` is not a field of a {self.verb} task."
                if spec.kind == "int":
                    try:
                        value = int(float(value))
                    except ValueError:
                        return f"Error: {field} must be a whole number."
                elif spec.kind == "float":
                    try:
                        value = float(value)
                    except ValueError:
                        return f"Error: {field} must be a number."
                self.fields[field] = value
            self.edits += 1
            return f"OK. {field} is now {value}."
        if name == "set_config":
            key = str(args.get("key", "")).strip().removeprefix("set ").strip()
            managed = MANAGED_KEYS.get(self.verb, {})
            if key in managed:
                return f"Error: {key} is controlled by {managed[key]}. Use set_field instead."
            flat = self._flat_config()
            if key not in flat:
                close = difflib.get_close_matches(key, list(flat), n=3, cutoff=0.5)
                return f"Error: {key} is not in the config." + (f" Close matches: {', '.join(close)}." if close else
                                                                 " Use find_config_keys to search.")
            raw = str(args.get("value", "")).strip()
            try:
                value = yaml.safe_load(raw)
            except Exception:  # noqa: BLE001
                return f"Error: could not read the value {raw!r}."
            self.sets[key] = value
            self.edits += 1
            return f"OK. {key} is now {format_value(value)} (preset had {format_value(flat[key])})."
        if name == "remove_config":
            key = str(args.get("key", "")).strip()
            if key not in self.sets:
                return f"Nothing to remove: there is no set line for {key}."
            del self.sets[key]
            self.edits += 1
            return f"OK. Removed the set line for {key}."
        if name == "find_config_keys":
            query = str(args.get("query", "")).lower()
            words = [_ALIASES.get(query, "")] + [_ALIASES.get(w, w) for w in re.findall(r"[a-z0-9_]+", query)]
            flat = self._flat_config()
            hits = [k for k in flat if any(w and w.lower() in k.lower() for w in words)]
            hits = hits or difflib.get_close_matches(query.upper(), list(flat), n=8, cutoff=0.3)
            return "\n".join(f"{k} = {format_value(flat[k])}" for k in hits[:15]) or "No matching keys."
        if name == "list_files":
            try:
                files = self.target.list_files(str(args.get("folder", "")), limit=40)
            except Exception as exc:  # noqa: BLE001
                return f"Error: could not list the folder ({str(exc)[:120]})."
            return "\n".join(files) or "No data or checkpoint files found there."
        return f"Error: unknown tool {name}."

    def task(self) -> dict[str, Any]:
        return {"verb": self.verb, "target": self.target_name, "fields": self.fields,
                "sets": [{"key": k, "value": v} for k, v in self.sets.items()]}


def _post_chat(messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> dict[str, Any]:
    body = {"model": DRAFT_MODEL, "stream": False, "messages": messages, "tools": tools, "think": "low",
            "options": {"temperature": 0, "num_ctx": 8192}}
    response = requests.post(f"{OLLAMA_URL}/api/chat", json=body, timeout=DRAFT_TIMEOUT)
    response.raise_for_status()
    return response.json().get("message", {})


def _system_for_agent() -> str:
    fields = {verb: [s.name for s in specs] for verb, specs in SCHEMA.items()}
    return (
        "You are the assistant inside a task-script editor for a biomedical segmentation app. The user reviews a "
        "script before it runs and talks to you about it.\n"
        f"Task kinds and their fields: {json.dumps(fields)}. Presets: {', '.join(PRESETS)}.\n"
        "`set KEY VALUE` lines override keys of the preset's YAML config.\n"
        "How the draft was made: files were picked from the folder listings and recent runs; steps defaults to 100 "
        "and preset to synthetic-tiny unless the user said otherwise; the output folder name is generated by code "
        "from the date and time.\n"
        "Rules:\n"
        "- When the user asks for a change, or agrees to one you suggested (\"do it\", \"yes\", \"go ahead\"), make it "
        "with the tools. Never say you changed something without calling a tool.\n"
        "- If you are not sure of a config key, call find_config_keys first. To look for files, call list_files.\n"
        "- Never invent file paths. Only use paths from the script, the facts, or list_files results.\n"
        "- When answering a question, be brief (1-3 sentences) and mention the script line number it concerns.\n"
        "- After editing, reply with one short sentence. The user will review your edits as a diff."
    )


def _step_text(name: str, args: dict[str, Any], out: str) -> dict[str, Any]:
    """One plain-language line per tool call, shown under the reply so the user can see what the agent did."""
    ok = not out.startswith("Error")
    tail = lambda p: "…/" + "/".join(str(p).rstrip("/").split("/")[-2:])  # noqa: E731
    if name == "set_field":
        value = args.get("value", "")
        value = tail(value) if str(value).startswith("/") else value
        text = f"Changed {args.get('name')} to {value}" if ok else f"Could not change {args.get('name')}: {out[7:]}"
    elif name == "set_config":
        reason = ("not in the config" if "not in the config" in out else
                  "set by a script line instead" if "controlled by" in out else "the value could not be read")
        text = f"Set {args.get('key')} to {args.get('value')}" if ok else f"Tried {args.get('key')}: {reason}"
    elif name == "remove_config":
        text = f"Removed the set line for {args.get('key')}" if ok else out
    elif name == "find_config_keys":
        n = 0 if out == "No matching keys." else len(out.splitlines())
        text = f"Searched the config for \u201c{args.get('query')}\u201d ({n} {'match' if n == 1 else 'matches'})"
    elif name == "list_files":
        n = 0 if not ok or out.startswith("No ") else len(out.splitlines())
        text = f"Listed {tail(args.get('folder', ''))} ({n} files)" if ok else f"Could not list {args.get('folder')}"
    else:
        text = f"{name}: {out[:80]}"
    return {"text": text, "ok": ok}


def converse(request: str, script_text: str, message: str, thread: list[dict[str, str]],
             task: dict[str, Any] | None, target, history: list[dict[str, Any]], draft_note: str = "") -> dict[str, Any]:
    from .compiler import PRESETS as _P
    from .language import check as _check_script

    started = time.time()
    task = task or {"verb": "train", "target": target.name, "fields": {}, "sets": []}
    inputs = {k: v for k, v in task.get("fields", {}).items() if k != "output"}
    folder_hint = request + " " + " ".join(
        str(v).rsplit("/", 1)[0] for v in inputs.values() if isinstance(v, str) and v.startswith("/"))
    context = gather_context(folder_hint, target, history)
    numbered = "\n".join(f"{i:>2} | {line}" for i, line in enumerate(script_text.splitlines(), start=1))

    messages: list[dict[str, Any]] = [
        {"role": "system", "content": _system_for_agent()},
        {"role": "user", "content": f"Facts: {json.dumps(context)}\nOriginal request: {request}\n"
                                    f"Note from the draft: {draft_note}\n"
                                    f"Current script (line numbers on the left):\n{numbered}"},
        {"role": "assistant", "content": "I have the script. What would you like to know or change?"},
    ]
    for turn in thread[-8:]:
        messages.append({"role": "user" if turn.get("role") == "user" else "assistant", "content": turn.get("text", "")})
    messages.append({"role": "user", "content": message})

    ws = _Workspace(task, target)
    tools = _tool_specs(ws.verb)
    steps: list[str] = []
    final_text = ""
    nudged = repaired = False
    try:
        for _ in range(MAX_TOOL_ROUNDS):
            reply = _post_chat(messages, tools)
            calls = reply.get("tool_calls") or []
            messages.append({"role": "assistant", "content": reply.get("content", ""), "tool_calls": calls})
            if calls:
                for call in calls:
                    fn = call.get("function", {})
                    name, args = fn.get("name", ""), fn.get("arguments") or {}
                    if isinstance(args, str):
                        try:
                            args = json.loads(args)
                        except json.JSONDecodeError:
                            args = {}
                    out = ws.run(name, args)
                    steps.append(_step_text(name, args, out))
                    messages.append({"role": "tool", "tool_name": name, "content": out})
                continue
            text = _clean_reply(reply.get("content", ""))
            if not ws.edits and not nudged and _PROMISE_RE.search(text):
                nudged = True  # it described a change without making it; ask it to act
                messages.append({"role": "user", "content": "You described a change but did not make it. "
                                                            "Make it now with the tools."})
                continue
            if ws.edits and not repaired:
                repaired = True
                _, diags = _check_script(render(ws.task()), _P)
                errors = [d for d in diags if d.severity == "error"]
                if errors:
                    messages.append({"role": "user", "content": "The checker found problems in your edit:\n" + "\n".join(
                        f"- line {d.line}: {d.message} {d.hint}" for d in errors) + "\nFix them with the tools."})
                    continue
            final_text = text
            break
    except Exception as exc:  # noqa: BLE001
        return {"kind": "error", "reply": f"Could not reach the drafting model ({str(exc)[:120]}). "
                                          "You can still edit the script directly.",
                "seconds": round(time.time() - started, 1), "steps": steps}

    result: dict[str, Any] = {"seconds": round(time.time() - started, 1), "steps": steps}
    if ws.edits:
        first = script_text.splitlines()[0] if script_text.strip() else ""
        comment = first[2:] if first.startswith("# ") else ""
        new_task = ws.task()
        result["script"] = render(new_task, comment=comment)
        summary = _describe_change(task, new_task["fields"], new_task["sets"])
        if new_task["target"] != task.get("target"):
            summary = f"Proposed: run on the {new_task['target']}." + (f" {summary}" if summary else "")
        result.update(kind="revise", reply=summary or "No changes were needed.")
    else:
        line = _LINE_RE.search(final_text)
        result.update(kind="answer", reply=final_text or "I could not come up with an answer. Try rephrasing.",
                      line=int(line.group(1)) if line else None)
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
