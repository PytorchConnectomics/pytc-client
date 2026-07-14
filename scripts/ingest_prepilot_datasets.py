#!/usr/bin/env python3
"""Ingest public PyTC prepilot datasets into project-shaped folders.

The goal is not to mirror every benchmark at full scale. It is to stage realistic
project folders that exercise the app's setup, agent, runtime, proofreading, and
evidence-export paths without silently depending on the old mito25 demo state.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import textwrap
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


SCRIPT_PATH = Path(__file__).resolve()
REPO_ROOT = SCRIPT_PATH.parents[1]
SEG_ROOT = REPO_ROOT.parent
DEFAULT_PROJECT_ROOT = SEG_ROOT / "testing_projects"
DEFAULT_DATA_ROOT = SEG_ROOT / "testing_data"
ALLOW_DOWNLOADS = True


@dataclass
class Role:
    name: str
    path: Path | None
    description: str
    hdf5_key: str | None = None

    def as_json(self, project_dir: Path) -> dict[str, Any]:
        if self.path is None:
            value = None
        else:
            try:
                value = str(self.path.resolve().relative_to(project_dir.resolve()))
            except ValueError:
                value = str(self.path.resolve())
        out: dict[str, Any] = {
            "name": self.name,
            "path": value,
            "description": self.description,
        }
        if self.hdf5_key:
            out["hdf5_key"] = self.hdf5_key
        return out


@dataclass
class ProjectSpec:
    slug: str
    title: str
    task: str
    source: str
    notes: list[str] = field(default_factory=list)
    roles: list[Role] = field(default_factory=list)
    recommended_configs: list[Path] = field(default_factory=list)
    source_urls: list[str] = field(default_factory=list)
    status: str = "ready"


def run(cmd: list[str], cwd: Path | None = None) -> None:
    print("+ " + " ".join(cmd), flush=True)
    subprocess.run(cmd, cwd=str(cwd) if cwd else None, check=True)


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def safe_unlink(path: Path) -> None:
    if path.is_symlink() or path.is_file():
        path.unlink()


def symlink_or_keep(src: Path, dst: Path) -> None:
    if not src.exists():
        raise FileNotFoundError(src)
    ensure_dir(dst.parent)
    if dst.exists() or dst.is_symlink():
        if dst.is_symlink() and dst.resolve() == src.resolve():
            return
        safe_unlink(dst)
    dst.symlink_to(src)


def copy_file(src: Path, dst: Path) -> None:
    if not src.exists():
        raise FileNotFoundError(src)
    ensure_dir(dst.parent)
    shutil.copy2(src, dst)


def download(url: str, dst: Path) -> None:
    ensure_dir(dst.parent)
    if dst.exists() and dst.stat().st_size > 0:
        print(f"Already downloaded: {dst}", flush=True)
        return
    if not ALLOW_DOWNLOADS:
        print(f"Download disabled, missing: {dst}", flush=True)
        return
    part = dst.with_suffix(dst.suffix + ".part")
    cmd = [
        "curl",
        "-L",
        "--fail",
        "--retry",
        "3",
        "--retry-delay",
        "2",
        "--continue-at",
        "-",
        "--output",
        str(part),
        url,
    ]
    run(cmd)
    part.rename(dst)


def extract_zip(zip_path: Path, dst: Path, delete_archive: bool = True) -> None:
    marker = dst / ".extract_complete"
    if marker.exists():
        print(f"Already extracted: {dst}", flush=True)
        if delete_archive and zip_path.exists():
            zip_path.unlink()
        return
    ensure_dir(dst)
    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(dst)
    marker.write_text("ok\n")
    if delete_archive:
        zip_path.unlink()


def free_bytes(path: Path) -> int:
    usage = shutil.disk_usage(path)
    return usage.free


def require_space(path: Path, needed_bytes: int, label: str) -> bool:
    free = free_bytes(path)
    if free < needed_bytes:
        print(
            f"Skipping {label}: needs about {needed_bytes / 1e9:.2f}GB free, "
            f"only {free / 1e9:.2f}GB available.",
            flush=True,
        )
        return False
    return True


def rel_or_abs(path: Path, base: Path) -> str:
    try:
        return str(path.resolve().relative_to(base.resolve()))
    except ValueError:
        return str(path.resolve())


def inspect_hdf5(path: Path, limit: int = 40) -> list[dict[str, Any]]:
    try:
        import h5py
    except Exception:
        return []

    datasets: list[dict[str, Any]] = []

    def visit(name: str, obj: Any) -> None:
        if len(datasets) >= limit:
            return
        if isinstance(obj, h5py.Dataset):
            datasets.append(
                {
                    "key": name,
                    "shape": list(obj.shape),
                    "dtype": str(obj.dtype),
                }
            )

    try:
        with h5py.File(path, "r") as handle:
            handle.visititems(visit)
    except Exception as exc:
        datasets.append({"error": repr(exc)})
    return datasets


def inspect_tiff(path: Path) -> dict[str, Any]:
    try:
        import tifffile

        with tifffile.TiffFile(path) as tif:
            series = tif.series[0]
            return {"shape": list(series.shape), "dtype": str(series.dtype)}
    except Exception as exc:
        return {"error": repr(exc)}


def write_manifest(project_dir: Path, spec: ProjectSpec) -> None:
    hdf5: dict[str, list[dict[str, Any]]] = {}
    tiff: dict[str, dict[str, Any]] = {}
    for file_path in sorted(project_dir.rglob("*")):
        if not file_path.is_file():
            continue
        suffix = file_path.suffix.lower()
        rel = rel_or_abs(file_path, project_dir)
        if suffix in {".h5", ".hdf", ".hdf5"}:
            hdf5[rel] = inspect_hdf5(file_path)
        elif suffix in {".tif", ".tiff"}:
            tiff[rel] = inspect_tiff(file_path)

    manifest = {
        "schema": "pytc-prepilot-project/v1",
        "slug": spec.slug,
        "title": spec.title,
        "task": spec.task,
        "source": spec.source,
        "status": spec.status,
        "source_urls": spec.source_urls,
        "roles": [role.as_json(project_dir) for role in spec.roles],
        "recommended_configs": [
            rel_or_abs(path, project_dir) for path in spec.recommended_configs if path.exists()
        ],
        "notes": spec.notes,
        "hdf5_inventory": hdf5,
        "tiff_inventory": tiff,
    }
    (project_dir / "project_manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    )

    notes_dir = ensure_dir(project_dir / "notes")
    readme = [
        f"# {spec.title}",
        "",
        f"Task: {spec.task}",
        f"Status: {spec.status}",
        f"Source: {spec.source}",
        "",
        "## Roles",
        "",
    ]
    for role in spec.roles:
        path_text = role.as_json(project_dir)["path"]
        key_text = f" HDF5 key: `{role.hdf5_key}`." if role.hdf5_key else ""
        readme.append(f"- `{role.name}`: `{path_text}`. {role.description}.{key_text}")
    readme += [
        "",
        "## Recommended Configs",
        "",
    ]
    if spec.recommended_configs:
        for config in spec.recommended_configs:
            readme.append(f"- `{rel_or_abs(config, project_dir)}`")
    else:
        readme.append("- No runnable config was written yet; see notes below.")
    readme += [
        "",
        "## Notes",
        "",
    ]
    for note in spec.notes:
        readme.append(f"- {note}")
    readme.append("")
    (notes_dir / "README.md").write_text("\n".join(readme))
    prepilot_log = notes_dir / "prepilot-log.md"
    if not prepilot_log.exists():
        prepilot_log.write_text(
            textwrap.dedent(
                """\
                # Prepilot Log

                | Check | Result | Evidence path | Notes |
                | --- | --- | --- | --- |
                | Project roles inferred correctly | pending |  |  |
                | Config selected correctly | pending |  |  |
                | Agent next-step answer useful | pending |  |  |
                | Agent action approval works | pending |  |  |
                | Runtime starts | pending |  |  |
                | Runtime summary readable | pending |  |  |
                | Proofreading loads quickly | pending |  |  |
                | Mask save persists | pending |  |  |
                | Export works | pending |  |  |
                | Candidate metrics computed | pending |  |  |
                | Evidence bundle exported | pending |  |  |
                """
            )
        )


def patch_yaml_text(src: Path, dst: Path, replacements: dict[str, str]) -> None:
    text = src.read_text()
    for old, new in replacements.items():
        text = text.replace(old, new)
    ensure_dir(dst.parent)
    dst.write_text(text)


def init_project(project_root: Path, slug: str) -> Path:
    project_dir = ensure_dir(project_root / slug)
    for child in ["data/image", "data/seg", "data/prediction", "configs", "checkpoints", "outputs", "notes"]:
        ensure_dir(project_dir / child)
    return project_dir


def stage_local_mito25_smoke(project_root: Path, data_root: Path) -> ProjectSpec:
    slug = "prepilot_mito25_smoke"
    project_dir = init_project(project_root, slug)
    source = data_root / "mito25_smoke"
    symlink_or_keep(source / "image", project_dir / "data/image/source")
    symlink_or_keep(source / "seg", project_dir / "data/seg/source")
    config = project_dir / "configs/Mito25-Local-Smoke-BC.yaml"
    copy_file(REPO_ROOT / "pytorch_connectomics/configs/MitoEM/Mito25-Local-Smoke-BC.yaml", config)
    spec = ProjectSpec(
        slug=slug,
        title="Prepilot Mito25 Smoke",
        task="Tiny local mitochondria instance-segmentation smoke loop",
        source=str(source),
        roles=[
            Role("dataset_path", project_dir / "data", "Project data root"),
            Role(
                "image_path",
                project_dir / "data/image/source/512-768_8192-10240_11264-13312_im.h5",
                "Training/proofreading image volume",
            ),
            Role(
                "label_path",
                project_dir / "data/seg/source/512-768_8192-10240_11264-13312_seg.h5",
                "Training/proofreading segmentation labels",
            ),
            Role(
                "inference_image_path",
                project_dir / "data/image/source/512-768_8192-10240_13312-15360_im.h5",
                "Held-out image volume for inference smoke",
            ),
        ],
        recommended_configs=[config],
        notes=[
            "Use first because it is fast and already aligned with the current app runtime configs.",
            "This fixture is not a biological generality test; it is an app closed-loop sanity test.",
        ],
    )
    write_manifest(project_dir, spec)
    return spec


def stage_local_snemi(project_root: Path, data_root: Path) -> ProjectSpec:
    slug = "prepilot_snemi3d_local"
    project_dir = init_project(project_root, slug)
    source = data_root / "snemi"
    symlink_or_keep(source / "image", project_dir / "data/image/source")
    symlink_or_keep(source / "seg", project_dir / "data/seg/source")
    config_base = project_dir / "configs/SNEMI-Prepilot-Base.yaml"
    src_base = REPO_ROOT / "pytorch_connectomics/configs/SNEMI/SNEMI-Base.yaml"
    text = src_base.read_text()
    text = text.replace("INPUT_PATH: datasets/SNEMI3D/ # or your own dataset path", f"INPUT_PATH: {project_dir / 'data'}")
    text = text.replace("OUTPUT_PATH: outputs/SNEMI3D/test", f"OUTPUT_PATH: {project_dir / 'outputs/inference'}")
    text = text.replace("OUTPUT_PATH: outputs/SNEMI3D/", f"OUTPUT_PATH: {project_dir / 'outputs/train'}")
    config_base.write_text(text)
    config_model = project_dir / "configs/SNEMI-Affinity-UNet.yaml"
    copy_file(REPO_ROOT / "pytorch_connectomics/configs/SNEMI/SNEMI-Affinity-UNet.yaml", config_model)
    spec = ProjectSpec(
        slug=slug,
        title="Prepilot SNEMI3D Local",
        task="Dense neurite affinity segmentation and postprocessing stress test",
        source=str(source),
        roles=[
            Role("dataset_path", project_dir / "data", "Project data root"),
            Role("image_path", project_dir / "data/image/source/train-input.tif", "Training image volume"),
            Role("label_path", project_dir / "data/seg/source/train-labels.tif", "Training segmentation labels"),
            Role("inference_image_path", project_dir / "data/image/source/test-input.tif", "Inference image volume"),
        ],
        recommended_configs=[config_base, config_model],
        notes=[
            "Affinity outputs are not directly editable instance masks; a robust agent should route through waterz/zwatershed.",
            "This local SNEMI fixture already existed, so it is symlinked rather than duplicated.",
        ],
        source_urls=["http://rhoana.rc.fas.harvard.edu/dataset/snemi.zip"],
    )
    write_manifest(project_dir, spec)
    return spec


def stage_mitoem_toy(project_root: Path) -> ProjectSpec:
    slug = "prepilot_mitoem_toy"
    project_dir = init_project(project_root, slug)
    image = project_dir / "data/image/mitoem_R_train_4um_im.h5"
    seg = project_dir / "data/seg/mitoem_R_train_4um_seg.h5"
    image_url = "https://huggingface.co/datasets/pytc/MitoEM/resolve/main/mitoem_R_train_4um_im.h5?download=true"
    seg_url = "https://huggingface.co/datasets/pytc/MitoEM/resolve/main/mitoem_R_train_4um_seg.h5?download=true"
    if require_space(project_root, 60_000_000, slug):
        download(image_url, image)
        download(seg_url, seg)
    config = project_dir / "configs/MitoEM-Toy-BC-Smoke.yaml"
    src = REPO_ROOT / "pytorch_connectomics/configs/MitoEM/Mito25-Local-Smoke-BC.yaml"
    text = src.read_text()
    old_train_im = "/Users/adamg/seg.bio/testing_data/mito25_smoke/image/512-768_8192-10240_11264-13312_im.h5"
    old_train_seg = "/Users/adamg/seg.bio/testing_data/mito25_smoke/seg/512-768_8192-10240_11264-13312_seg.h5"
    old_infer_im = "/Users/adamg/seg.bio/testing_data/mito25_smoke/image/512-768_8192-10240_13312-15360_im.h5"
    old_output = "/Users/adamg/seg.bio/outputs/mito25_local_smoke_bc"
    text = text.replace(old_train_im, str(image))
    text = text.replace(old_train_seg, str(seg))
    text = text.replace(old_infer_im, str(image))
    text = text.replace(old_output, str(project_dir / "outputs/mitoem_toy_bc"))
    config.write_text(text)
    spec = ProjectSpec(
        slug=slug,
        title="Prepilot MitoEM Toy Crop",
        task="Real public mitochondria instance-segmentation crop",
        source="pytc/MitoEM Hugging Face dataset",
        roles=[
            Role("dataset_path", project_dir / "data", "Project data root"),
            Role("image_path", image, "4um MitoEM-R raw image HDF5 crop"),
            Role("label_path", seg, "4um MitoEM-R mitochondria instance labels"),
        ],
        recommended_configs=[config],
        source_urls=[image_url, seg_url],
        notes=[
            "Use this as the first non-demo project-agnostic role-inference test.",
            "The smoke config intentionally uses the same image for training and inference so runtime plumbing can be tested quickly.",
        ],
    )
    write_manifest(project_dir, spec)
    return spec


def find_first(root: Path, names: list[str]) -> Path | None:
    lowered = {name.lower() for name in names}
    for path in sorted(root.rglob("*")):
        if path.is_file() and path.name.lower() in lowered:
            return path
    return None


def stage_lucchi(project_root: Path) -> ProjectSpec:
    slug = "prepilot_lucchi_pp"
    project_dir = init_project(project_root, slug)
    archive = project_dir / ".cache/lucchi_pp.zip"
    source_dir = project_dir / "data/source"
    url = "https://huggingface.co/datasets/pytc/tutorial/resolve/main/lucchi%2B%2B.zip?download=true"
    if require_space(project_root, 800_000_000, slug):
        if (source_dir / ".extract_complete").exists():
            print(f"Already extracted: {source_dir}", flush=True)
        else:
            download(url, archive)
            extract_zip(archive, source_dir)

    candidates = {
        "train_im": find_first(source_dir, ["train_im.tif", "train_im.h5"]),
        "train_label": find_first(
            source_dir,
            ["train_label.tif", "train_label.h5", "train_mito.tif", "train_mito.h5"],
        ),
        "test_im": find_first(source_dir, ["test_im.tif", "test_im.h5"]),
        "test_label": find_first(
            source_dir,
            ["test_label.tif", "test_label.h5", "test_mito.tif", "test_mito.h5"],
        ),
    }
    role_paths: dict[str, Path | None] = {
        "train_im": None,
        "train_label": None,
        "test_im": None,
        "test_label": None,
    }
    if candidates["train_im"]:
        role_paths["train_im"] = project_dir / f"data/image/{candidates['train_im'].name}"
        symlink_or_keep(candidates["train_im"], role_paths["train_im"])
    if candidates["test_im"]:
        role_paths["test_im"] = project_dir / f"data/image/{candidates['test_im'].name}"
        symlink_or_keep(candidates["test_im"], role_paths["test_im"])
    if candidates["train_label"]:
        role_paths["train_label"] = project_dir / f"data/seg/{candidates['train_label'].name}"
        symlink_or_keep(candidates["train_label"], role_paths["train_label"])
    if candidates["test_label"]:
        role_paths["test_label"] = project_dir / f"data/seg/{candidates['test_label'].name}"
        symlink_or_keep(candidates["test_label"], role_paths["test_label"])

    config = project_dir / "configs/Lucchi-Prepilot-Mitochondria.yaml"
    src = REPO_ROOT / "pytorch_connectomics/configs/Lucchi-Mitochondria.yaml"
    text = src.read_text()
    train_im_name = role_paths["train_im"].name if role_paths["train_im"] else "train_im.tif"
    train_label_name = role_paths["train_label"].name if role_paths["train_label"] else "train_label.tif"
    test_im_name = role_paths["test_im"].name if role_paths["test_im"] else "test_im.tif"
    text = text.replace("INPUT_PATH: datasets/Lucchi/", f"INPUT_PATH: {project_dir / 'data'}")
    text = text.replace("IMAGE_NAME: img/train_im.tif", f"IMAGE_NAME: image/{train_im_name}")
    text = text.replace("LABEL_NAME: label/train_label.tif", f"LABEL_NAME: seg/{train_label_name}")
    text = text.replace("IMAGE_NAME: img/test_im.tif", f"IMAGE_NAME: image/{test_im_name}")
    text = text.replace("OUTPUT_PATH: outputs/Lucchi_UNet/test", f"OUTPUT_PATH: {project_dir / 'outputs/inference'}")
    text = text.replace("OUTPUT_PATH: outputs/Lucchi_UNet/", f"OUTPUT_PATH: {project_dir / 'outputs/train'}")
    config.write_text(text)
    spec = ProjectSpec(
        slug=slug,
        title="Prepilot Lucchi++",
        task="Mitochondria semantic segmentation benchmark",
        source="pytc/tutorial Hugging Face dataset",
        roles=[
            Role("dataset_path", project_dir / "data", "Project data root"),
            Role("image_path", role_paths["train_im"], "Training image stack"),
            Role("label_path", role_paths["train_label"], "Training semantic mitochondria labels"),
            Role("inference_image_path", role_paths["test_im"], "Test image stack"),
            Role("reference_label_path", role_paths["test_label"], "Test labels if present"),
        ],
        recommended_configs=[config],
        source_urls=[url],
        notes=[
            "This is a semantic-mask project, not an instance-queue proofreading project.",
            "If file names differ after upstream archive changes, inspect data/source and update role links.",
        ],
    )
    write_manifest(project_dir, spec)
    return spec


def stage_cremi(project_root: Path) -> ProjectSpec:
    slug = "prepilot_cremi_official"
    project_dir = init_project(project_root, slug)
    urls = {
        "sample_A_20160501.hdf": "https://cremi.org/static/data/sample_A_20160501.hdf",
        "sample_B_20160501.hdf": "https://cremi.org/static/data/sample_B_20160501.hdf",
        "sample_C_20160501.hdf": "https://cremi.org/static/data/sample_C_20160501.hdf",
    }
    if require_space(project_root, 700_000_000, slug):
        for name, url in urls.items():
            download(url, project_dir / "data/source" / name)
    config_base = project_dir / "configs/CREMI-Official-Base.yaml"
    copy_file(REPO_ROOT / "pytorch_connectomics/configs/CREMI/CREMI-Base.yaml", config_base)
    config_model = project_dir / "configs/CREMI-Foreground-UNet.yaml"
    copy_file(REPO_ROOT / "pytorch_connectomics/configs/CREMI/CREMI-Foreground-UNet.yaml", config_model)
    spec = ProjectSpec(
        slug=slug,
        title="Prepilot CREMI Official Crops",
        task="Synaptic cleft detection and HDF5-key stress test",
        source="CREMI challenge official cropped datasets",
        roles=[
            Role("dataset_path", project_dir / "data/source", "Official CREMI HDF5 containers"),
            Role(
                "image_path",
                project_dir / "data/source/sample_A_20160501.hdf",
                "Sample A raw volume container",
                hdf5_key="volumes/raw",
            ),
            Role(
                "label_path",
                project_dir / "data/source/sample_A_20160501.hdf",
                "Sample A synaptic cleft labels in the same HDF5 container",
                hdf5_key="volumes/labels/clefts",
            ),
        ],
        recommended_configs=[config_base, config_model],
        source_urls=list(urls.values()),
        status="needs-preprocessing",
        notes=[
            "Official CREMI data stores raw, clefts, neuron ids, and annotations inside each HDF5 file.",
            "The legacy local PyTC config expects preprocessed corrected/im_A.h5 and corrected/syn_A.h5 style files, so this project intentionally exposes an HDF5-key/config-adaptation gap.",
            "Use this fixture to test whether the app asks for HDF5 keys instead of pretending the container is one simple volume.",
        ],
    )
    write_manifest(project_dir, spec)
    return spec


def stage_nucmm_mouse(project_root: Path) -> ProjectSpec:
    slug = "prepilot_nucmm_mouse"
    project_dir = init_project(project_root, slug)
    archive = project_dir / ".cache/NucMM-M.zip"
    source_dir = project_dir / "data/source"
    url = "https://huggingface.co/datasets/pytc/NucMM/resolve/main/NucMM-M.zip?download=true"
    if require_space(project_root, 1_500_000_000, slug):
        if (source_dir / ".extract_complete").exists():
            print(f"Already extracted: {source_dir}", flush=True)
        else:
            download(url, archive)
            extract_zip(archive, source_dir)
    config_base = project_dir / "configs/NucMM-Mouse-Base.yaml"
    copy_file(REPO_ROOT / "pytorch_connectomics/configs/NucMM/NucMM-Mouse-Base.yaml", config_base)
    config_model = project_dir / "configs/NucMM-Mouse-UNet-BC.yaml"
    copy_file(REPO_ROOT / "pytorch_connectomics/configs/NucMM/NucMM-Mouse-UNet-BC.yaml", config_model)

    h5_files = sorted(source_dir.rglob("*.h5"))
    image_guess = next((p for p in h5_files if p.name.startswith(("img", "im_"))), None)
    seg_guess = next((p for p in h5_files if p.name.startswith(("seg", "nuc"))), None)
    if image_guess:
        symlink_or_keep(image_guess, project_dir / f"data/image/{image_guess.name}")
    if seg_guess:
        symlink_or_keep(seg_guess, project_dir / f"data/seg/{seg_guess.name}")

    spec = ProjectSpec(
        slug=slug,
        title="Prepilot NucMM Mouse",
        task="Neuronal nuclei instance segmentation generality test",
        source="pytc/NucMM Hugging Face dataset",
        roles=[
            Role("dataset_path", project_dir / "data", "Project data root"),
            Role("image_path", project_dir / f"data/image/{image_guess.name}" if image_guess else None, "Guessed mouse nuclei image volume"),
            Role("label_path", project_dir / f"data/seg/{seg_guess.name}" if seg_guess else None, "Guessed mouse nuclei label volume"),
        ],
        recommended_configs=[config_base, config_model],
        source_urls=[url],
        status="needs-confirmation" if not image_guess or not seg_guess else "ready",
        notes=[
            "Use this to force non-mito language and project-general workflow behavior.",
            "The manifest records guessed roles; confirm them in the app before mutating workflow state.",
            "The upstream archive layout may not exactly match the legacy config paths.",
        ],
    )
    write_manifest(project_dir, spec)
    return spec


def write_index(project_root: Path, specs: list[ProjectSpec]) -> None:
    ensure_dir(project_root)
    lines = [
        "# Prepilot Projects",
        "",
        "Generated by `pytc-client/scripts/ingest_prepilot_datasets.py`.",
        "",
        "| Project | Task | Status | Notes |",
        "| --- | --- | --- | --- |",
    ]
    for spec in specs:
        note = spec.notes[0] if spec.notes else ""
        lines.append(f"| `{spec.slug}` | {spec.task} | {spec.status} | {note} |")
    lines.append("")
    lines.append("Large datasets intentionally omitted unless they fit local disk constraints: full MitoEM, MitoEM2.0, padded CREMI, and NucMM-Z.")
    lines.append("")
    (project_root / "README.md").write_text("\n".join(lines))


def main() -> None:
    global ALLOW_DOWNLOADS
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, default=DEFAULT_PROJECT_ROOT)
    parser.add_argument("--data-root", type=Path, default=DEFAULT_DATA_ROOT)
    parser.add_argument("--skip-downloads", action="store_true")
    parser.add_argument("--skip-nucmm", action="store_true")
    parser.add_argument("--skip-cremi", action="store_true")
    parser.add_argument("--skip-lucchi", action="store_true")
    args = parser.parse_args()
    ALLOW_DOWNLOADS = not args.skip_downloads

    project_root = ensure_dir(args.project_root)
    specs: list[ProjectSpec] = []
    specs.append(stage_local_mito25_smoke(project_root, args.data_root))
    specs.append(stage_local_snemi(project_root, args.data_root))

    specs.append(stage_mitoem_toy(project_root))
    if not args.skip_lucchi:
        specs.append(stage_lucchi(project_root))
    if not args.skip_cremi:
        specs.append(stage_cremi(project_root))
    if not args.skip_nucmm:
        specs.append(stage_nucmm_mouse(project_root))

    write_index(project_root, specs)
    print("\nPrepilot project root:", project_root)
    for spec in specs:
        print(f"- {spec.slug}: {spec.status}")


if __name__ == "__main__":
    main()
