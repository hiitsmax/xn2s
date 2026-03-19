from __future__ import annotations

import json
from pathlib import Path


DEFAULT_UI_STATE_PATH = Path("data/ui_state.json")


def _default_doc() -> dict[str, str]:
    return {"appearance_mode": "system"}


def load_ui_state(path: Path | None = None) -> dict[str, str]:
    storage_path = path or DEFAULT_UI_STATE_PATH
    if not storage_path.exists():
        return _default_doc()

    try:
        payload = json.loads(storage_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return _default_doc()

    if not isinstance(payload, dict):
        return _default_doc()

    appearance_mode = payload.get("appearance_mode")
    if not isinstance(appearance_mode, str):
        return _default_doc()
    return {"appearance_mode": appearance_mode}


def save_ui_state(state: dict[str, str], path: Path | None = None) -> None:
    storage_path = path or DEFAULT_UI_STATE_PATH
    storage_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = storage_path.with_name(f".{storage_path.name}.tmp")
    temp_path.write_text(
        f"{json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True)}\n",
        encoding="utf-8",
    )
    temp_path.replace(storage_path)
