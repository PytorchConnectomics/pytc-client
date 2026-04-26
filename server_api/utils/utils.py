import pathlib

MOUNT_VARIANT_SUFFIXES = (
    "_im",
    "_image",
    "_img",
    "_seg",
    "_mask",
    "_label",
    "_gt",
)


def _normalized_variant_name(name):
    candidate = pathlib.Path(name)
    stem = candidate.stem.lower()
    suffix = candidate.suffix.lower()
    for token in MOUNT_VARIANT_SUFFIXES:
        if stem.endswith(token):
            stem = stem[: -len(token)]
            break
    return stem, suffix


def resolve_existing_path(path):
    if not path:
        return None

    candidate = pathlib.Path(path).expanduser()
    if candidate.exists():
        return candidate

    parent = candidate.parent
    if not parent.exists() or not parent.is_dir():
        return candidate

    target_is_file = candidate.suffix != ""
    normalized_stem, normalized_suffix = _normalized_variant_name(candidate.name)
    matches = []

    for child in parent.iterdir():
        if target_is_file and not child.is_file():
            continue
        if not target_is_file and not child.is_dir():
            continue

        child_stem, child_suffix = _normalized_variant_name(child.name)
        if target_is_file and child_suffix != normalized_suffix:
            continue
        if child_stem == normalized_stem:
            matches.append(child)

    if len(matches) == 1:
        return matches[0]

    return candidate


def process_path(path):
    if not path:
        return None
    candidate = pathlib.Path(path).expanduser()
    if candidate.is_absolute():
        return resolve_existing_path(candidate)
    return resolve_existing_path(candidate.resolve(strict=False))
