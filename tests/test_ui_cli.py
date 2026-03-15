from __future__ import annotations

from pathlib import Path

import pytest
import typer

from xs2n.cli.ui import ui


def test_ui_command_launches_browser(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    captured: dict[str, object] = {}

    def fake_launcher(**kwargs):
        captured.update(kwargs)

    monkeypatch.setattr("xs2n.cli.ui._load_ui_launcher", lambda: fake_launcher)

    ui(
        data_dir=tmp_path / "data",
        run_id="20260315T203138Z",
    )

    assert captured == {
        "data_dir": tmp_path / "data",
        "initial_run_id": "20260315T203138Z",
    }


def test_ui_command_uses_default_data_dir(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def fake_launcher(**kwargs):
        captured.update(kwargs)

    monkeypatch.setattr("xs2n.cli.ui._load_ui_launcher", lambda: fake_launcher)

    ui()

    assert captured["data_dir"] == Path("data")
    assert captured["initial_run_id"] is None


def test_ui_command_surfaces_missing_dependency(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        "xs2n.cli.ui._load_ui_launcher",
        lambda: (_ for _ in ()).throw(ImportError("missing fltk")),
    )
    monkeypatch.setattr("xs2n.cli.ui.sys.platform", "darwin")

    with pytest.raises(typer.Exit) as error:
        ui()

    assert error.value.exit_code == 1
    captured = capsys.readouterr()
    assert "uv sync --extra gui" in captured.err
    assert "brew install fltk" in captured.err
