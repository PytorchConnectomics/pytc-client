#!/usr/bin/env python3
"""Create the deterministic local project used by the development app."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from server_api.synthetic_project import create_synthetic_project


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        default=str(REPO_ROOT / ".pytc/synthetic-core-project"),
        help="Project directory (default: .pytc/synthetic-core-project)",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Delete and restore the generated project to its canonical state.",
    )
    args = parser.parse_args()
    print(
        json.dumps(
            create_synthetic_project(args.output_dir, reset=args.reset),
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
