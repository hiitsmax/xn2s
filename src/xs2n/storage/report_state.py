from __future__ import annotations

import json
from pathlib import Path
from typing import Any


DEFAULT_REPORT_STATE_PATH = Path("data/report_state.json")


def _empty_doc() -> dict[str, Any]:
    return {"last_run_at": None, "threads": {}}


def load_report_state(path: Path | None = None) -> dict[str, Any]:
    storage_path = path or DEFAULT_REPORT_STATE_PATH
    if not storage_path.exists():
        return _empty_doc()

    try:
        data = json.loads(storage_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return _empty_doc()

    if not isinstance(data, dict):
        return _empty_doc()
    threads = data.get("threads")
    if not isinstance(threads, dict):
        data["threads"] = {}
    if "last_run_at" not in data:
        data["last_run_at"] = None
    return data


def save_report_state(doc: dict[str, Any], path: Path | None = None) -> None:
    storage_path = path or DEFAULT_REPORT_STATE_PATH
    storage_path.parent.mkdir(parents=True, exist_ok=True)
    storage_path.write_text(
        f"{json.dumps(doc, ensure_ascii=False, indent=2)}\n",
        encoding="utf-8",
    )
