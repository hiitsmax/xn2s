from __future__ import annotations

import json
from pathlib import Path
from typing import Any


DEFAULT_ONBOARD_STATE_PATH = Path("data/onboard_state.json")


def load_onboard_state(path: Path | None = None) -> dict[str, str]:
    storage_path = path or DEFAULT_ONBOARD_STATE_PATH
    if not storage_path.exists():
        return {}

    try:
        data = json.loads(storage_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}

    if not isinstance(data, dict):
        return {}
    return {
        str(key): str(value)
        for key, value in data.items()
        if isinstance(value, (str, int, float))
    }


def save_onboard_state(state: dict[str, str], path: Path | None = None) -> None:
    storage_path = path or DEFAULT_ONBOARD_STATE_PATH
    storage_path.parent.mkdir(parents=True, exist_ok=True)
    storage_path.write_text(
        f"{json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True)}\n",
        encoding="utf-8",
    )


def resolve_onboard_state_path(
    parameters: dict[str, Any],
    default_path: Path | None = None,
) -> Path:
    override = parameters.get("onboard_state_file")
    if isinstance(override, Path):
        return override
    return default_path or DEFAULT_ONBOARD_STATE_PATH
