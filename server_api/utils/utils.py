import pathlib

def process_path(path):
    if not path:
        return None
    candidate = pathlib.Path(path).expanduser()
    if candidate.is_absolute():
        return candidate
    return candidate.resolve(strict=False)