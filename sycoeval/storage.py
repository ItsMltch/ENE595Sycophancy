"""Read the item list and read/write transcript files (JSON Lines, one conversation per line)."""

import csv
import json
import threading
from pathlib import Path


def load_items(path: Path) -> list[dict]:
    with open(path, encoding="utf-8-sig", newline="") as f:  # utf-8-sig: the CSV has an Excel BOM
        return list(csv.DictReader(f))


def append_record(path: Path, record: dict, lock: threading.Lock | None = None) -> None:
    """Append one record. Existing lines are never rewritten."""
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(record, ensure_ascii=False) + "\n"
    if lock:
        with lock, open(path, "a", encoding="utf-8") as f:
            f.write(line)
    else:
        with open(path, "a", encoding="utf-8") as f:
            f.write(line)


def load_records(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def latest_ok(records: list[dict]) -> dict[str, dict]:
    """Map run_key -> the most recent successful record. Failed attempts are kept in the file but skipped here."""
    out = {}
    for r in records:
        if r["status"] == "ok":
            out[r["run_key"]] = r
    return out


def total_cost(records: list[dict]) -> float:
    return sum(r.get("total_cost_usd") or 0.0 for r in records)
