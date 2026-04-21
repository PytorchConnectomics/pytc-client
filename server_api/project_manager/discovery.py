from __future__ import annotations

import pathlib
from collections import Counter
from typing import Dict, List

SUPPORTED_VOLUME_FILE_SUFFIXES = (
    ".nii.gz",
    ".hdf5",
    ".tiff",
    ".h5",
    ".tif",
    ".nii",
    ".mrc",
)
SUPPORTED_VOLUME_DIR_SUFFIXES = (".zarr", ".n5")
SUPPORTED_STACK_IMAGE_SUFFIXES = (".tif", ".tiff", ".png", ".jpg", ".jpeg")

PROJECT_MANAGER_SUPPORTED_VOLUME_INPUTS = [
    ".h5",
    ".hdf5",
    ".tif",
    ".tiff",
    ".nii",
    ".nii.gz",
    ".mrc",
    ".zarr",
    ".n5",
    "image-stack directories with .png/.jpg/.jpeg/.tif/.tiff slices",
]


def _is_hidden_path(root: pathlib.Path, path: pathlib.Path) -> bool:
    if path == root:
        return False
    parts = path.relative_to(root).parts
    return any(part.startswith(".") or part == "__pycache__" for part in parts)


def _match_supported_suffix(
    path: pathlib.Path, suffixes: tuple[str, ...]
) -> str | None:
    lowered = path.name.lower()
    for suffix in sorted(suffixes, key=len, reverse=True):
        if lowered.endswith(suffix):
            return suffix
    return None


def _discover_from_dir(
    root: pathlib.Path, current: pathlib.Path
) -> List[Dict[str, str]]:
    if _is_hidden_path(root, current):
        return []

    if current != root:
        container_suffix = _match_supported_suffix(
            current, SUPPORTED_VOLUME_DIR_SUFFIXES
        )
        if container_suffix:
            rel_path = str(current.relative_to(root))
            return [
                {
                    "rel_path": rel_path,
                    "filename": current.name,
                    "format": container_suffix,
                    "kind": "container",
                    "path": str(current),
                }
            ]

    entries = sorted(current.iterdir(), key=lambda entry: entry.name.lower())
    files = [
        entry
        for entry in entries
        if entry.is_file() and not _is_hidden_path(root, entry)
    ]
    dirs = [
        entry
        for entry in entries
        if entry.is_dir() and not _is_hidden_path(root, entry)
    ]

    stack_slice_files = [
        entry
        for entry in files
        if _match_supported_suffix(entry, SUPPORTED_STACK_IMAGE_SUFFIXES)
    ]
    if current != root and len(stack_slice_files) >= 2 and len(stack_slice_files) == len(files):
        rel_path = str(current.relative_to(root))
        return [
            {
                "rel_path": rel_path,
                "filename": current.name,
                "format": "image_stack",
                "kind": "image_stack",
                "path": str(current),
            }
        ]

    discovered: List[Dict[str, str]] = []
    for file_path in files:
        file_suffix = _match_supported_suffix(file_path, SUPPORTED_VOLUME_FILE_SUFFIXES)
        if not file_suffix:
            continue
        rel_path = str(file_path.relative_to(root))
        discovered.append(
            {
                "rel_path": rel_path,
                "filename": file_path.name,
                "format": file_suffix,
                "kind": "file",
                "path": str(file_path),
            }
        )

    for dir_path in dirs:
        discovered.extend(_discover_from_dir(root, dir_path))

    return discovered


def discover_project_manager_volumes(root: pathlib.Path) -> List[Dict[str, str]]:
    resolved_root = root.expanduser().resolve()
    return _discover_from_dir(resolved_root, resolved_root)


def summarize_discovered_formats(entries: List[Dict[str, str]]) -> Dict[str, int]:
    return dict(Counter(entry["format"] for entry in entries))
