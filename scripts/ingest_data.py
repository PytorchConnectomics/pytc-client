import json
import os
import pathlib
import sys

from server_api.project_manager.discovery import (
    PROJECT_MANAGER_SUPPORTED_VOLUME_INPUTS,
    discover_project_manager_volumes,
    summarize_discovered_formats,
)


def ingest(data_root: str, json_path: str):
    root = pathlib.Path(data_root).expanduser().resolve()
    path = pathlib.Path(json_path).resolve()

    if not root.exists():
        print(f"Error: Data root not found at {root}")
        return

    # Load existing data
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"Error reading JSON: {e}")
            return
    else:
        data = {}

    existing_volumes = data.get("volumes", [])
    # Create lookup for existing volumes to preserve assignee/status
    vol_map = {v["rel_path"]: v for v in existing_volumes if "rel_path" in v}
    # Also handle ID-based lookup if rel_path is missing but ID looks like a path
    for v in existing_volumes:
        if "rel_path" not in v and "id" in v:
            vol_map[v["id"]] = v

    new_volumes = []
    discovered_entries = discover_project_manager_volumes(root)
    format_counts = summarize_discovered_formats(discovered_entries)
    print(
        "Crawling "
        f"{root} for supported project volumes "
        f"({', '.join(PROJECT_MANAGER_SUPPORTED_VOLUME_INPUTS)})..."
    )

    for entry in discovered_entries:
        rel_path = entry["rel_path"]
        filename = entry["filename"]

        # Check if we already have this volume
        if rel_path in vol_map:
            vol = vol_map[rel_path]
            # Update basic info if needed, but preserve state
            vol["filename"] = filename
            vol["id"] = rel_path
            vol["rel_path"] = rel_path
            new_volumes.append(vol)
        else:
            # Create new volume record
            new_volumes.append(
                {
                    "id": rel_path,
                    "filename": filename,
                    "rel_path": rel_path,
                    "assignee": None,
                    "status": "todo",
                }
            )

    data["volumes"] = new_volumes

    # Optional: Update project_info if it's a new file
    if "project_info" not in data:
        data["project_info"] = {
            "name": root.name,
            "description": f"Imported from {root}",
            "version": "1.0.0",
        }

    try:
        path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        print(f"Successfully ingested {len(new_volumes)} volumes into {path}")
        if format_counts:
            summary = ", ".join(
                f"{fmt}: {count}" for fmt, count in sorted(format_counts.items())
            )
            print(f"Detected formats: {summary}")
    except Exception as e:
        print(f"Error writing JSON: {e}")


if __name__ == "__main__":
    DATA_ROOT = os.environ.get("DATA_ROOT_EM")
    JSON_PATH = os.environ.get("PROJECT_METADATA_JSON")

    if not DATA_ROOT or not JSON_PATH:
        print("Error: DATA_ROOT_EM and PROJECT_METADATA_JSON must be set.")
        sys.exit(1)

    ingest(DATA_ROOT, JSON_PATH)
