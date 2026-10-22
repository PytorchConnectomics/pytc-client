"""PyTC task scripts: a small, line-based language for one workflow task.

Example::

    # Drafted from: "train a model on my data in dsl-demo"
    task train on cluster
      image   "/data/train-01_image.h5"
      label   "/data/train-01_ground_truth.h5"
      preset  synthetic-tiny
      steps   200
      output  "/runs/mito-01"

Grammar (one task per script for now)::

    script  := (blank | comment)* header (field | blank | comment)*
    header  := "task" VERB ["on" TARGET]
    field   := INDENT NAME VALUE
    VALUE   := "quoted string" | NUMBER | IDENTIFIER

Parsing and checking are deterministic. The LLM only drafts text that goes
through the same checker as hand-written scripts.
"""

from __future__ import annotations

import difflib
import json
import re
from pathlib import Path
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

VERBS = ("train", "infer", "evaluate", "view")
TARGETS = ("cluster", "laptop")
DEFAULT_TARGET = "cluster"


@dataclass(frozen=True)
class FieldSpec:
    name: str
    kind: str  # path | int | float | preset
    required: bool
    help: str
    default: Any = None
    minimum: Optional[float] = None
    maximum: Optional[float] = None
    suffixes: tuple[str, ...] = ()


SCHEMA: dict[str, tuple[FieldSpec, ...]] = {
    "train": (
        FieldSpec("image", "path", True, "Training image volume (.h5 or .tif)"),
        FieldSpec("label", "path", True, "Ground-truth labels for the image"),
        FieldSpec("preset", "preset", True, "Base model configuration", "synthetic-tiny"),
        FieldSpec("steps", "int", False, "Training iterations", 100, 1, 200000),
        FieldSpec("output", "path", True, "Folder for checkpoints and logs"),
    ),
    "infer": (
        FieldSpec("model", "path", True, "Trained checkpoint", suffixes=(".pth.tar", ".pth")),
        FieldSpec("image", "path", True, "Image volume to segment"),
        FieldSpec("preset", "preset", True, "Configuration the model was trained with", "synthetic-tiny"),
        FieldSpec("output", "path", True, "Folder for the prediction"),
    ),
    "evaluate": (
        FieldSpec("prediction", "path", True, "Prediction to score"),
        FieldSpec("truth", "path", True, "Ground-truth labels"),
        FieldSpec("baseline", "path", False, "Older prediction to compare against"),
        FieldSpec("threshold", "float", False, "Foreground threshold, 0 to 1", 0.5, 0.0, 1.0),
    ),
    "view": (
        FieldSpec("image", "path", True, "Image volume to open in Neuroglancer"),
        FieldSpec("label", "path", False, "Segmentation or prediction to overlay"),
    ),
}


@dataclass
class Diagnostic:
    line: int  # 1-based
    severity: str  # error | warning | info
    message: str
    hint: str = ""
    col: int = 1  # 1-based
    end_col: int = 0
    code: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "line": self.line,
            "col": self.col,
            "end_col": self.end_col,
            "severity": self.severity,
            "message": self.message,
            "hint": self.hint,
            "code": self.code,
        }


@dataclass
class FieldValue:
    name: str
    value: Any
    raw: str
    quoted: bool
    line: int
    col: int
    name_col: int = 1


@dataclass
class SetLine:
    """`set SOLVER.BASE_LR 0.001`: change any key of the preset's YAML config."""

    key: str
    value: Any
    raw: str
    line: int
    key_col: int
    value_col: int


@dataclass
class TaskScript:
    verb: str
    target: str
    header_line: int
    fields: dict[str, FieldValue] = field(default_factory=dict)
    sets: list[SetLine] = field(default_factory=list)

    def get(self, name: str, default: Any = None) -> Any:
        if name in self.fields:
            return self.fields[name].value
        spec = spec_for(self.verb, name)
        if spec is not None and spec.default is not None:
            return spec.default
        return default

    def as_dict(self) -> dict[str, Any]:
        return {
            "verb": self.verb,
            "target": self.target,
            "fields": {name: f.value for name, f in self.fields.items()},
            "sets": [{"key": s.key, "value": s.value} for s in self.sets],
        }


def spec_for(verb: str, name: str) -> Optional[FieldSpec]:
    for spec in SCHEMA.get(verb, ()):
        if spec.name == name:
            return spec
    return None


_HEADER_RE = re.compile(r"^task(?:\s+(?P<verb>\S+))?(?:\s+on\s+(?P<target>\S+))?\s*(?P<rest>.*)$")
_FIELD_RE = re.compile(r"^(?P<indent>\s+)(?P<name>[A-Za-z_][\w-]*)(?:\s+(?P<value>.*?))?\s*$")
_IDENT_RE = re.compile(r"^[A-Za-z0-9_.\-/~]+$")


def _strip_comment(text: str) -> str:
    in_quote = False
    for index, char in enumerate(text):
        if char == '"':
            in_quote = not in_quote
        elif char == "#" and not in_quote:
            return text[:index].rstrip()
    return text.rstrip()


def _close(word: str, options) -> str:
    match = difflib.get_close_matches(word, list(options), n=1, cutoff=0.6)
    return f"Did you mean `{match[0]}`?" if match else ""


def _parse_value(raw: str) -> tuple[Any, bool, Optional[str]]:
    """Return (value, quoted, error)."""
    if raw.startswith('"'):
        if len(raw) < 2 or not raw.endswith('"'):
            return None, True, "This text is missing its closing quote."
        inner = raw[1:-1]
        if '"' in inner:
            return None, True, "Only one quoted value is allowed per line."
        return inner, True, None
    if re.fullmatch(r"-?\d+", raw):
        return int(raw), False, None
    if re.fullmatch(r"-?\d*\.\d+", raw):
        return float(raw), False, None
    if " " in raw.strip():
        return None, False, "Values with spaces must be in double quotes."
    if not _IDENT_RE.match(raw):
        return None, False, "This value has characters that need double quotes."
    return raw, False, None


def parse(text: str) -> tuple[Optional[TaskScript], list[Diagnostic]]:
    """Syntax pass. Never raises; returns diagnostics instead."""
    diags: list[Diagnostic] = []
    script: Optional[TaskScript] = None
    for number, original in enumerate(text.splitlines(), start=1):
        line = _strip_comment(original)
        if not line.strip():
            continue
        if not line[0].isspace():
            match = _HEADER_RE.match(line)
            if not line.startswith("task") or not match or not line[4:5].isspace() and len(line) > 4:
                word = line.split()[0]
                diags.append(Diagnostic(number, "error", f"Expected a line starting with `task`, found `{word}`.",
                                        "Scripts start with a header such as `task train on cluster`. "
                                        "Fields below it must be indented.", 1, len(word) + 1, "syntax.header"))
                if script is None:  # keep reading fields so one bad header doesn't hide everything else
                    script = TaskScript(verb="?", target=DEFAULT_TARGET, header_line=number)
                continue
            if script is not None:
                diags.append(Diagnostic(number, "error", "Only one task per script for now.",
                                        "Split this into separate scripts and run them one after another.",
                                        1, len(line) + 1, "syntax.multiple_tasks"))
                continue
            verb = match.group("verb")
            target = match.group("target") or DEFAULT_TARGET
            if not verb:
                diags.append(Diagnostic(number, "error", "The task is missing its kind.",
                                        f"Use one of: {', '.join(VERBS)}.", 1, len(line) + 1, "syntax.verb_missing"))
                verb = "?"
            elif verb not in VERBS:
                col = line.index(verb) + 1
                diags.append(Diagnostic(number, "error", f"Unknown task `{verb}`.",
                                        _close(verb, VERBS) or f"Use one of: {', '.join(VERBS)}.",
                                        col, col + len(verb), "syntax.verb_unknown"))
            if match.group("target") and target not in TARGETS:
                col = line.rindex(target) + 1
                diags.append(Diagnostic(number, "error", f"Unknown place to run `{target}`.",
                                        _close(target, TARGETS) or f"Use `on cluster` or `on laptop`.",
                                        col, col + len(target), "syntax.target_unknown"))
            if match.group("rest"):
                rest = match.group("rest")
                col = line.rindex(rest) + 1
                diags.append(Diagnostic(number, "error", f"Unexpected text `{rest}` after the task header.",
                                        "The header is `task <kind> on <cluster|laptop>`.",
                                        col, col + len(rest), "syntax.header_extra"))
            script = TaskScript(verb=verb, target=target, header_line=number)
            continue

        if script is None:
            diags.append(Diagnostic(number, "error", "This field comes before any `task` header.",
                                    "Put `task <kind> on cluster` on the first line.", 1, len(line) + 1,
                                    "syntax.field_before_header"))
            continue
        match = _FIELD_RE.match(line)
        if not match:
            diags.append(Diagnostic(number, "error", "Could not read this line.",
                                    "Each field is a name followed by a value, for example `steps 200`.",
                                    1, len(line) + 1, "syntax.field"))
            continue
        name = match.group("name")
        raw = (match.group("value") or "").strip()
        col = len(match.group("indent")) + 1
        if name == "set":
            _parse_set(script, raw, line, number, col, diags)
            continue
        if not raw:
            diags.append(Diagnostic(number, "error", f"`{name}` has no value.",
                                    "Write the value after the field name.", col, col + len(name),
                                    "syntax.value_missing"))
            continue
        value, quoted, error = _parse_value(raw)
        value_col = line.index(raw, col - 1 + len(name)) + 1
        if error:
            diags.append(Diagnostic(number, "error", error, "", value_col, value_col + len(raw), "syntax.value"))
            continue
        if name in script.fields:
            diags.append(Diagnostic(number, "error", f"`{name}` is set twice.",
                                    f"It was already set on line {script.fields[name].line}.",
                                    col, col + len(name), "syntax.duplicate"))
            continue
        script.fields[name] = FieldValue(name, value, raw, quoted, number, value_col, col)

    if script is None and not diags:
        diags.append(Diagnostic(1, "error", "The script is empty.",
                                "Start with a header such as `task train on cluster`.", 1, 1, "syntax.empty"))
    return script, diags


_SET_RE = re.compile(r"^(?P<key>[A-Za-z_][\w]*(?:\.[A-Za-z_][\w]*)+)(?:\s+(?P<value>.+))?$")


def _parse_set(script: "TaskScript", raw: str, line: str, number: int, col: int, diags: list) -> None:
    match = _SET_RE.match(raw)
    if not match:
        diags.append(Diagnostic(number, "error", "A `set` line needs a config key and a value.",
                                "For example `set SOLVER.BASE_LR 0.001`.", col, len(line) + 1, "syntax.set"))
        return
    key, value_raw = match.group("key"), (match.group("value") or "").strip()
    key_col = line.index(key, col + 2) + 1
    if not value_raw:
        diags.append(Diagnostic(number, "error", f"`set {key}` has no value.", "Write the new value after the key.",
                                key_col, key_col + len(key), "syntax.set_value"))
        return
    value_col = line.index(value_raw, key_col - 1 + len(key)) + 1
    try:
        import yaml

        value = yaml.safe_load(value_raw)
    except Exception:  # noqa: BLE001 - any YAML problem is a syntax error on this line
        diags.append(Diagnostic(number, "error", f"Could not read the value `{value_raw}`.",
                                "Use a number, true/false, text, or a list like [8, 16, 32].",
                                value_col, value_col + len(value_raw), "syntax.set_value"))
        return
    for other in script.sets:
        if other.key == key:
            diags.append(Diagnostic(number, "error", f"`{key}` is set twice.", f"It was already set on line {other.line}.",
                                    key_col, key_col + len(key), "syntax.duplicate"))
            return
    script.sets.append(SetLine(key, value, value_raw, number, key_col, value_col))


# Config keys that a named field already controls. `set` may not override them.
MANAGED_KEYS = {
    "train": {"DATASET.IMAGE_NAME": "image", "DATASET.LABEL_NAME": "label", "DATASET.OUTPUT_PATH": "output",
              "SOLVER.ITERATION_TOTAL": "steps", "SYSTEM.NUM_GPUS": "the `on cluster` / `on laptop` header"},
    "infer": {"INFERENCE.IMAGE_NAME": "image", "INFERENCE.OUTPUT_PATH": "output",
              "SYSTEM.NUM_GPUS": "the `on cluster` / `on laptop` header"},
}


def _flatten(cfg: Any, prefix: str = "") -> dict[str, Any]:
    out: dict[str, Any] = {}
    if isinstance(cfg, dict):
        for k, v in cfg.items():
            key = f"{prefix}.{k}" if prefix else str(k)
            if isinstance(v, dict):
                out.update(_flatten(v, key))
            else:
                out[key] = v
    return out


def _same_kind(old: Any, new: Any) -> bool:
    if old is None:
        return True
    if isinstance(old, bool) or isinstance(new, bool):
        return isinstance(old, bool) and isinstance(new, bool)
    if isinstance(old, (int, float)):
        return isinstance(new, (int, float))
    if isinstance(old, list):
        return isinstance(new, list)
    if isinstance(old, str):
        return isinstance(new, str)
    return True


def _kind_name(value: Any) -> str:
    if isinstance(value, bool):
        return "true or false"
    if isinstance(value, (int, float)):
        return "a number"
    if isinstance(value, list):
        return "a list like [1, 2, 3]"
    return "text"


def _check_sets(script: "TaskScript", presets: dict[str, Any], diags: list) -> None:
    if not script.sets:
        return
    if script.verb not in MANAGED_KEYS:
        for s in script.sets:
            diags.append(Diagnostic(s.line, "error", f"`set` only works for train and infer tasks.", "",
                                    s.key_col, s.key_col + len(s.key), "meaning.set_verb"))
        return
    preset = script.get("preset")
    if preset not in presets:
        return  # the preset line already has an error
    import yaml

    flat = _flatten(yaml.safe_load(Path(presets[preset]).read_text()) or {})
    for s in script.sets:
        end = s.key_col + len(s.key)
        if s.key in MANAGED_KEYS[script.verb]:
            diags.append(Diagnostic(s.line, "error", f"`{s.key}` comes from {MANAGED_KEYS[script.verb][s.key]}.",
                                    "Change that line instead, so the script has one place for each setting.",
                                    s.key_col, end, "meaning.set_managed"))
        elif s.key not in flat:
            diags.append(Diagnostic(s.line, "error", f"`{s.key}` is not in the `{preset}` config.",
                                    _close(s.key, flat) or "Open the config.yaml tab to see the available keys.",
                                    s.key_col, end, "meaning.set_key"))
        elif not _same_kind(flat[s.key], s.value):
            diags.append(Diagnostic(s.line, "error", f"`{s.key}` should be {_kind_name(flat[s.key])}.",
                                    f"The preset has `{json.dumps(flat[s.key])}`.", s.value_col,
                                    s.value_col + len(s.raw), "meaning.set_type"))


PathChecker = Callable[[str, list[str]], dict[str, bool]]


def check(
    text: str,
    presets: dict[str, Any],
    path_checker: Optional[PathChecker] = None,
) -> tuple[Optional[TaskScript], list[Diagnostic]]:
    """Syntax pass, then meaning pass (fields, types, ranges, and paths)."""
    script, diags = parse(text)
    if script is None or script.verb not in SCHEMA or any(d.severity == "error" and d.code.startswith("syntax.header") for d in diags):
        return script, diags

    specs = {spec.name: spec for spec in SCHEMA[script.verb]}
    for name, fv in script.fields.items():
        if name not in specs:
            diags.append(Diagnostic(fv.line, "error", f"`{name}` is not a setting for `task {script.verb}`.",
                                    _close(name, specs) or f"Settings for {script.verb}: {', '.join(specs)}.",
                                    fv.name_col, fv.name_col + len(name), "meaning.unknown_field"))
    for spec in specs.values():
        if spec.required and spec.name not in script.fields and spec.default is None:
            diags.append(Diagnostic(script.header_line, "error", f"`task {script.verb}` needs `{spec.name}`.",
                                    f"Add a line like `  {spec.name} {_example(spec)}` ({spec.help}).",
                                    1, 0, "meaning.missing_field"))

    paths_to_check: list[tuple[FieldValue, FieldSpec]] = []
    for name, fv in script.fields.items():
        spec = specs.get(name)
        if spec is None:
            continue
        end = fv.col + len(fv.raw)
        if spec.kind == "path":
            if not fv.quoted or not isinstance(fv.value, str):
                diags.append(Diagnostic(fv.line, "error", f"`{name}` must be a path in double quotes.",
                                        f'For example `{name} "/projects/lab/data.h5"`.', fv.col, end,
                                        "meaning.path_unquoted"))
                continue
            if not fv.value.strip():
                diags.append(Diagnostic(fv.line, "error", f"`{name}` is empty.",
                                        f"Fill in a full path: {spec.help.lower()}.", fv.col, end,
                                        "meaning.path_empty"))
                continue
            if not fv.value.startswith(("/", "~")):
                diags.append(Diagnostic(fv.line, "error", f"`{name}` must be a full path starting with `/`.",
                                        "Relative paths are ambiguous on the cluster.", fv.col, end,
                                        "meaning.path_relative"))
                continue
            if spec.suffixes and not fv.value.endswith(spec.suffixes):
                diags.append(Diagnostic(fv.line, "error", f"`{name}` should be a checkpoint file.",
                                        f"Expected a file ending in {' or '.join(spec.suffixes)}.", fv.col, end,
                                        "meaning.path_suffix"))
                continue
            paths_to_check.append((fv, spec))
        elif spec.kind in ("int", "float"):
            ok = isinstance(fv.value, int) if spec.kind == "int" else isinstance(fv.value, (int, float))
            if not ok or isinstance(fv.value, bool):
                diags.append(Diagnostic(fv.line, "error", f"`{name}` must be a {'whole number' if spec.kind == 'int' else 'number'}.",
                                        f"For example `{name} {spec.default}`.", fv.col, end, "meaning.type"))
                continue
            if spec.minimum is not None and fv.value < spec.minimum or spec.maximum is not None and fv.value > spec.maximum:
                diags.append(Diagnostic(fv.line, "error", f"`{name}` must be between {spec.minimum:g} and {spec.maximum:g}.",
                                        "", fv.col, end, "meaning.range"))
        elif spec.kind == "preset":
            if fv.quoted or fv.value not in presets:
                diags.append(Diagnostic(fv.line, "error", f"Unknown preset `{fv.value}`.",
                                        _close(str(fv.value), presets) or f"Available presets: {', '.join(presets)}.",
                                        fv.col, end, "meaning.preset"))

    _check_sets(script, presets, diags)

    if path_checker and paths_to_check:
        try:
            results = path_checker(script.target, [fv.value for fv, _ in paths_to_check])
        except Exception as exc:  # noqa: BLE001 - surface any connection problem as a diagnostic
            diags.append(Diagnostic(script.header_line, "warning", f"Could not check paths on the {script.target}: {exc}",
                                    "The run may fail if a path is wrong.", 1, 0, "meaning.path_unchecked"))
            results = {}
        for fv, spec in paths_to_check:
            is_output = spec.name == "output"
            exists = results.get(fv.value)
            if exists is None:
                continue
            if is_output:
                parent = fv.value.rstrip("/").rsplit("/", 1)[0] or "/"
                if not results.get(parent, True):
                    diags.append(Diagnostic(fv.line, "warning", f"`{parent}` does not exist on the {script.target} yet. It will be created.",
                                            "If that folder name is a typo, fix it before running.",
                                            fv.col, fv.col + len(fv.raw), "meaning.output_parent"))
                elif exists:
                    diags.append(Diagnostic(fv.line, "warning", "This output folder already exists. Files in it may be overwritten.",
                                            "Pick a new folder name to keep earlier results.",
                                            fv.col, fv.col + len(fv.raw), "meaning.output_exists"))
            elif not exists:
                diags.append(Diagnostic(fv.line, "error", f"`{fv.value}` was not found on the {script.target}.",
                                        "Check the spelling, or copy the file there first.",
                                        fv.col, fv.col + len(fv.raw), "meaning.path_missing"))
    diags.sort(key=lambda d: (d.line, d.col))
    return script, diags


def output_parents(script: TaskScript) -> list[str]:
    out = script.fields.get("output")
    if out and isinstance(out.value, str):
        return [out.value.rstrip("/").rsplit("/", 1)[0] or "/"]
    return []


def _example(spec: FieldSpec) -> str:
    if spec.kind == "path":
        return '"/path/to/file"'
    if spec.default is not None:
        return str(spec.default)
    return "..."


def render(task: dict[str, Any], comment: str = "") -> str:
    """Deterministic printer: structured task -> script text."""
    verb = task.get("verb", "train")
    target = task.get("target") or DEFAULT_TARGET
    values = task.get("fields", {})
    lines = []
    if comment:
        lines.append(f"# {comment}")
    lines.append(f"task {verb} on {target}")
    specs = SCHEMA.get(verb, ())
    width = max((len(s.name) for s in specs), default=6)
    for spec in specs:
        value = values.get(spec.name)
        if value in (None, ""):
            if spec.required and spec.default is None:
                lines.append(f"  {spec.name.ljust(width)}  \"\"   # TODO: {spec.help.lower()}")
            continue
        text = f'"{value}"' if spec.kind == "path" else str(value)
        lines.append(f"  {spec.name.ljust(width)}  {text}")
    for item in task.get("sets", []) or []:
        lines.append(f"  set {item['key']} {format_value(item['value'])}")
    return "\n".join(lines) + "\n"


def format_value(value: Any) -> str:
    """Print a `set` value so the parser reads it back unchanged."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return "null"
    if isinstance(value, (int, float)):
        return repr(value)
    if isinstance(value, list):
        return "[" + ", ".join(format_value(v) for v in value) + "]"
    text = str(value)
    return text if re.fullmatch(r"[A-Za-z_][\w.-]*", text) and text not in ("true", "false", "null") else json.dumps(text)
