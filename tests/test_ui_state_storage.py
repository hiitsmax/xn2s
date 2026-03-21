from __future__ import annotations

import json
from pathlib import Path

from xs2n.storage.ui_state import load_ui_state, save_ui_state


def test_load_ui_state_defaults_to_system_when_missing(tmp_path: Path) -> None:
    assert load_ui_state(tmp_path / "missing.json") == {
        "appearance_mode": "system",
        "digest_navigation_visible": False,
    }


def test_load_ui_state_defaults_to_system_for_invalid_json(tmp_path: Path) -> None:
    state_path = tmp_path / "ui_state.json"
    state_path.write_text("{not json", encoding="utf-8")

    assert load_ui_state(state_path) == {
        "appearance_mode": "system",
        "digest_navigation_visible": False,
    }


def test_save_ui_state_roundtrips_appearance_mode(tmp_path: Path) -> None:
    state_path = tmp_path / "ui_state.json"

    save_ui_state(
        {
            "appearance_mode": "classic_dark",
            "digest_navigation_visible": True,
        },
        state_path,
    )

    assert json.loads(state_path.read_text(encoding="utf-8")) == {
        "appearance_mode": "classic_dark",
        "digest_navigation_visible": True,
    }
    assert load_ui_state(state_path) == {
        "appearance_mode": "classic_dark",
        "digest_navigation_visible": True,
    }
