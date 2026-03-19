from __future__ import annotations

from pathlib import Path

import pytest
import typer

from xs2n.cli.ui import ui
from xs2n.cli import ui as ui_module


def test_ui_command_launches_browser(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    captured: dict[str, object] = {}

    def fake_launcher(**kwargs):
        captured.update(kwargs)

    monkeypatch.setattr("xs2n.cli.ui._load_ui_launcher", lambda: fake_launcher)
    monkeypatch.setattr(
        "xs2n.cli.ui.relaunch_ui_from_app_bundle",
        lambda **kwargs: False,
    )

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
    monkeypatch.setattr(
        "xs2n.cli.ui.relaunch_ui_from_app_bundle",
        lambda **kwargs: False,
    )

    ui()

    assert captured["data_dir"] == Path("data")
    assert captured["initial_run_id"] is None


def test_ui_command_surfaces_missing_dependency(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        "xs2n.cli.ui.relaunch_ui_from_app_bundle",
        lambda **kwargs: False,
    )
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


def test_ui_command_relaunches_bundled_app_on_macos(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}
    launch_calls: list[dict[str, object]] = []

    def fake_launcher(**kwargs):
        launch_calls.append(kwargs)

    monkeypatch.setattr(
        "xs2n.cli.ui.relaunch_ui_from_app_bundle",
        lambda **kwargs: captured.update(kwargs) or True,
    )
    monkeypatch.setattr("xs2n.cli.ui._load_ui_launcher", lambda: fake_launcher)

    ui(
        data_dir=Path("data"),
        run_id="20260315T203138Z",
    )

    assert captured["data_dir"] == Path("data")
    assert captured["run_id"] == "20260315T203138Z"
    assert captured["repo_root"].name == "xs2n"
    assert launch_calls == []


def test_ui_command_checks_dependencies_before_bundle_relaunch(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr("xs2n.cli.ui.sys.platform", "darwin")
    monkeypatch.setattr(
        "xs2n.cli.ui.relaunch_ui_from_app_bundle",
        lambda **kwargs: (_ for _ in ()).throw(
            AssertionError("should not relaunch before dependency check")
        ),
    )
    monkeypatch.setattr(
        "xs2n.cli.ui._load_ui_launcher",
        lambda: (_ for _ in ()).throw(ImportError("missing fltk")),
    )

    with pytest.raises(typer.Exit) as error:
        ui()

    assert error.value.exit_code == 1
    captured = capsys.readouterr()
    assert "uv sync --extra gui" in captured.err
    assert "brew install fltk" in captured.err


def test_load_ui_launcher_imports_browser(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_launcher(**kwargs):
        return kwargs

    monkeypatch.setitem(
        __import__("sys").modules,
        "xs2n.ui.app",
        type(
            "FakeAppModule",
            (),
            {"run_artifact_browser": staticmethod(fake_launcher)},
        ),
    )

    launcher = ui_module._load_ui_launcher()

    assert callable(launcher)
    assert launcher is fake_launcher
