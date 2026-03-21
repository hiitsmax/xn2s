from __future__ import annotations

from pathlib import Path

from .sources import _load_json_doc, _save_json_doc


DEFAULT_UI_STATE_PATH = Path("data/ui_state.json")


def _default_doc() -> dict[str, str | bool]:
    return {
        "appearance_mode": "system",
        "digest_navigation_visible": False,
    }


def load_ui_state(path: Path | None = None) -> dict[str, str | bool]:
    storage_path = path or DEFAULT_UI_STATE_PATH
    payload = _load_json_doc(storage_path, default_factory=_default_doc)

    if not isinstance(payload, dict):
        return _default_doc()

    appearance_mode = payload.get("appearance_mode")
    digest_navigation_visible = payload.get("digest_navigation_visible")
    if not isinstance(appearance_mode, str):
        appearance_mode = _default_doc()["appearance_mode"]
    if not isinstance(digest_navigation_visible, bool):
        digest_navigation_visible = _default_doc()["digest_navigation_visible"]
    return {
        "appearance_mode": appearance_mode,
        "digest_navigation_visible": digest_navigation_visible,
    }


def save_ui_state(state: dict[str, str | bool], path: Path | None = None) -> None:
    storage_path = path or DEFAULT_UI_STATE_PATH
    _save_json_doc(state, storage_path, sort_keys=True)
