from __future__ import annotations

from pathlib import Path
from typing import Any

from .sources import _load_json_doc, _save_json_doc


DEFAULT_REPORT_STATE_PATH = Path("data/report_state.json")


def _empty_doc() -> dict[str, Any]:
    return {"last_run_at": None, "threads": {}}


def load_report_state(path: Path | None = None) -> dict[str, Any]:
    storage_path = path or DEFAULT_REPORT_STATE_PATH
    data = _load_json_doc(storage_path, default_factory=_empty_doc)

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
    _save_json_doc(doc, storage_path)
