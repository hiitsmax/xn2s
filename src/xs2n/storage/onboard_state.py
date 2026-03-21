from __future__ import annotations

from pathlib import Path
from typing import Any

from .sources import _load_json_doc, _save_json_doc


DEFAULT_ONBOARD_STATE_PATH = Path("data/onboard_state.json")


def load_onboard_state(path: Path | None = None) -> dict[str, str]:
    storage_path = path or DEFAULT_ONBOARD_STATE_PATH
    data = _load_json_doc(storage_path, default_factory=dict)

    if not isinstance(data, dict):
        return {}
    return {
        str(key): str(value)
        for key, value in data.items()
        if isinstance(value, (str, int, float))
    }


def save_onboard_state(state: dict[str, str], path: Path | None = None) -> None:
    storage_path = path or DEFAULT_ONBOARD_STATE_PATH
    _save_json_doc(state, storage_path, sort_keys=True)


def resolve_onboard_state_path(
    parameters: dict[str, Any],
    default_path: Path | None = None,
) -> Path:
    override = parameters.get("onboard_state_file")
    if isinstance(override, Path):
        return override
    return default_path or DEFAULT_ONBOARD_STATE_PATH
