import yaml

from server_api.task_dsl.compiler import PRESETS, compile_script
from server_api.task_dsl.language import check, parse, render

TRAIN = """# Drafted from: "train on my data"
task train on cluster
  image   "/data/train-01_image.h5"
  label   "/data/train-01_ground_truth.h5"
  preset  synthetic-tiny
  steps   50
  output  "/runs/mito-01"
"""


def codes(diags):
    return [d.code for d in diags if d.severity == "error"]


def test_valid_train_script_compiles_to_config_with_overrides():
    script, diags = check(TRAIN, PRESETS)
    assert codes(diags) == []
    plan = compile_script(script)
    cfg = yaml.safe_load(plan.files["config.yaml"])
    assert cfg["DATASET"]["IMAGE_NAME"] == "/data/train-01_image.h5"
    assert cfg["SOLVER"]["ITERATION_TOTAL"] == 50
    assert cfg["SYSTEM"]["NUM_GPUS"] == 1
    assert plan.outputs["checkpoint"] == "/runs/mito-01/checkpoint_00050.pth.tar"


def test_compiler_auto_fixes_known_runtime_failures_and_says_so():
    script, _ = check(TRAIN, PRESETS)
    plan = compile_script(script)
    cfg = yaml.safe_load(plan.files["config.yaml"])
    assert all(f % 8 == 0 for f in cfg["MODEL"]["FILTERS"])
    assert cfg["INFERENCE"]["AUG_NUM"] == 0
    fixed = {c["key"] for c in plan.changes if c["source"] == "auto-fix"}
    assert {"MODEL.FILTERS", "INFERENCE.AUG_NUM"} <= fixed


def test_typo_in_field_name_is_flagged_on_its_line_with_suggestion():
    _, diags = check(TRAIN.replace("steps   50", "stpes   50"), PRESETS)
    [d] = [d for d in diags if d.severity == "error"]
    assert d.line == 6 and d.code == "meaning.unknown_field" and "steps" in d.hint


def test_syntax_errors_are_reported_without_raising():
    broken = TRAIN.replace('"/runs/mito-01"', '"/runs/mito-01').replace("task train", "tsk train")
    _, diags = parse(broken)
    assert "syntax.header" in codes(diags)
    assert "syntax.value" in codes(diags)


def test_missing_required_field_and_bad_values_are_errors():
    text = 'task infer on laptop\n  image "data.h5"\n  preset tiny\n  output "/out"\n'
    _, diags = check(text, PRESETS)
    assert {"meaning.missing_field", "meaning.path_relative", "meaning.preset"} <= set(codes(diags))


def test_path_checker_flags_missing_inputs_and_existing_outputs():
    def fake(target, paths):
        return {p: p != "/data/train-01_ground_truth.h5" for p in paths}

    _, diags = check(TRAIN, PRESETS, fake)
    assert codes(diags) == ["meaning.path_missing"]
    assert any(d.code == "meaning.output_exists" for d in diags)


def test_render_round_trips_through_the_checker():
    text = render({"verb": "evaluate", "target": "laptop",
                   "fields": {"prediction": "/p.h5", "truth": "/t.h5", "threshold": 0.4}})
    script, diags = check(text, PRESETS)
    assert codes(diags) == []
    assert script.get("threshold") == 0.4


def test_set_lines_change_any_preset_key_and_are_checked():
    text = TRAIN + "  set SOLVER.BASE_LR 0.001\n  set MODEL.FILTERS [8, 16, 24, 32, 40]\n"
    script, diags = check(text, PRESETS)
    assert codes(diags) == []
    plan = compile_script(script)
    cfg = yaml.safe_load(plan.files["config.yaml"])
    assert cfg["SOLVER"]["BASE_LR"] == 0.001
    assert cfg["MODEL"]["FILTERS"] == [8, 16, 24, 32, 40]
    assert any(c["key"] == "SOLVER.BASE_LR" and c["source"] == "script" for c in plan.changes)


def test_set_lines_reject_typos_wrong_types_and_managed_keys():
    text = TRAIN + "  set SOLVER.BASE_RL 0.001\n  set SOLVER.BASE_LR fast\n  set SOLVER.ITERATION_TOTAL 5\n"
    _, diags = check(text, PRESETS)
    errs = {d.code: d for d in diags if d.severity == "error"}
    assert "SOLVER.BASE_LR" in errs["meaning.set_key"].hint
    assert "meaning.set_type" in errs and "meaning.set_managed" in errs


def test_render_prints_set_lines_that_parse_back():
    text = render({"verb": "train", "target": "cluster",
                   "fields": {"image": "/i.h5", "label": "/l.h5", "output": "/o"},
                   "sets": [{"key": "SOLVER.BASE_LR", "value": 0.001}, {"key": "MODEL.FILTERS", "value": [8, 16]}]})
    script, diags = check(text, PRESETS)
    assert codes(diags) == []
    assert [(s.key, s.value) for s in script.sets] == [("SOLVER.BASE_LR", 0.001), ("MODEL.FILTERS", [8, 16])]
