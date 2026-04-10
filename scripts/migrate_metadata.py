#!/usr/bin/env python3
"""
Migration Utility: Kanchan's Logic
Updates volume assignees to 'kanchan' for volumes under a specific subdirectory.
"""

import json
import argparse
import pathlib

def migrate(json_path: str, target_subdir: str = "1440/"):
    path = pathlib.Path(json_path).resolve()
    if not path.exists():
        print(f"Error: File not found at {path}")
        return

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"Error reading JSON: {e}")
        return

    volumes = data.get("volumes", [])
    updated_count = 0

    for vol in volumes:
        rel_path = vol.get("rel_path", "")
        if target_subdir in rel_path:
            vol["assignee"] = "kanchan"
            updated_count += 1

    if updated_count > 0:
        try:
            path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
            print(f"Successfully updated {updated_count} volumes to assignee 'kanchan'.")
        except Exception as e:
            print(f"Error writing JSON: {e}")
    else:
        print(f"No volumes found matching subdirectory '{target_subdir}'.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Migrate volume assignees based on subdirectory.")
    parser.add_argument("json_path", help="Path to the project_manager_data.json file")
    parser.add_argument("--subdir", default="1440/", help="Subdirectory to match in rel_path (default: 1440/)")
    
    args = parser.parse_args()
    migrate(args.json_path, args.subdir)
