#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path


DEFAULT_LOG = Path(__file__).resolve().parents[1] / ".logs" / "app" / "app-events.jsonl"


def load_rows(path: Path):
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def summarize(rows, *, session_id: str | None = None, last: int = 12):
    if session_id:
        rows = [row for row in rows if row.get("session_id") == session_id]

    if not rows:
        print("No matching log rows.")
        return

    components = Counter(row.get("component", "?") for row in rows)
    events = Counter(row.get("event", "?") for row in rows)
    levels = Counter(row.get("level", "?") for row in rows)
    sessions = Counter(row.get("session_id") for row in rows if row.get("session_id"))

    print(f"rows: {len(rows)}")
    print(f"first: {rows[0].get('timestamp')}")
    print(f"last:  {rows[-1].get('timestamp')}")
    if sessions and not session_id:
        print(f"sessions: {dict(sessions)}")

    print("\ncomponents:")
    for name, count in components.most_common():
        print(f"  {name}: {count}")

    print("\nlevels:")
    for name, count in levels.most_common():
        print(f"  {name}: {count}")

    print("\ntop events:")
    for name, count in events.most_common(12):
        print(f"  {name}: {count}")

    print("\npossible issues:")
    issue_rows = [
        row
        for row in rows
        if row.get("level") == "ERROR"
        or row.get("event") in {"api_response_error", "window_error", "unhandled_rejection"}
    ]
    if not issue_rows:
        print("  none")
    else:
        for row in issue_rows[:12]:
            print(
                f"  {row.get('timestamp')} {row.get('component')} "
                f"{row.get('event')}: {row.get('message')}"
            )

    print("\nrecent:")
    for row in rows[-last:]:
        print(
            f"  {row.get('timestamp')} {row.get('component')} "
            f"{row.get('event')}: {row.get('message')}"
        )


def main():
    parser = argparse.ArgumentParser(description="Summarize PyTC app event logs")
    parser.add_argument("--log", default=str(DEFAULT_LOG), help="Path to app-events.jsonl")
    parser.add_argument("--session", default=None, help="Optional client session_id filter")
    parser.add_argument("--last", type=int, default=12, help="Recent rows to print")
    args = parser.parse_args()

    log_path = Path(args.log).expanduser().resolve(strict=False)
    if not log_path.is_file():
        raise SystemExit(f"Log file not found: {log_path}")

    summarize(load_rows(log_path), session_id=args.session, last=args.last)


if __name__ == "__main__":
    main()
