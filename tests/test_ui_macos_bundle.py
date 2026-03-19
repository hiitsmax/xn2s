from __future__ import annotations

import os
from pathlib import Path

import pytest

from xs2n.ui.macos.bundle import (
    BUNDLE_EXECUTABLE_NAME,
    BUNDLED_ENV_VAR,
    _build_info_plist,
    _build_launcher_script,
    _ensure_ui_bundle,
    relaunch_ui_from_app_bundle,
)


class _FakeStream:
    def __init__(self, is_tty: bool) -> None:
        self._is_tty = is_tty

    def isatty(self) -> bool:
        return self._is_tty


def test_build_info_plist_uses_xn2s_identity() -> None:
    info_plist = _build_info_plist()

    assert info_plist["CFBundleName"] == "xn2s"
    assert info_plist["CFBundleDisplayName"] == "xn2s"
    assert info_plist["CFBundleExecutable"] == BUNDLE_EXECUTABLE_NAME


def test_build_launcher_script_marks_bundled_launch(tmp_path: Path) -> None:
    script = _build_launcher_script(
        repo_root=tmp_path,
        python_executable=Path("/tmp/demo-python"),
    )

    assert f"export {BUNDLED_ENV_VAR}=1" in script
    assert " -m xs2n.cli.cli ui " in script
    assert str(tmp_path) in script


def test_ensure_ui_bundle_writes_bundle_files(tmp_path: Path) -> None:
    bundle_path = _ensure_ui_bundle(
        repo_root=tmp_path,
        python_executable=Path("/tmp/demo-python"),
    )

    assert bundle_path.name == "xn2s.app"
    assert (bundle_path / "Contents" / "Info.plist").exists()
    launcher_path = bundle_path / "Contents" / "MacOS" / BUNDLE_EXECUTABLE_NAME
    assert launcher_path.exists()
    assert os.access(launcher_path, os.X_OK)


def test_relaunch_ui_from_app_bundle_skips_when_already_bundled(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr("xs2n.ui.macos.bundle.sys.platform", "darwin")
    monkeypatch.setenv(BUNDLED_ENV_VAR, "1")
    monkeypatch.setattr(
        "xs2n.ui.macos.bundle.subprocess.Popen",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("should not launch")
        ),
    )

    assert (
        relaunch_ui_from_app_bundle(
            repo_root=tmp_path,
            data_dir=tmp_path / "data",
            run_id=None,
        )
        is False
    )


def test_relaunch_ui_from_app_bundle_launches_open(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    captured: dict[str, object] = {}

    monkeypatch.setattr("xs2n.ui.macos.bundle.sys.platform", "darwin")
    monkeypatch.setattr("xs2n.ui.macos.bundle.sys.stdin", _FakeStream(False))
    monkeypatch.setattr("xs2n.ui.macos.bundle.sys.stdout", _FakeStream(False))
    monkeypatch.setattr("xs2n.ui.macos.bundle.sys.stderr", _FakeStream(False))

    def fake_popen(command, **kwargs):
        captured["command"] = command
        captured["kwargs"] = kwargs
        return object()

    monkeypatch.setattr("xs2n.ui.macos.bundle.subprocess.Popen", fake_popen)

    assert (
        relaunch_ui_from_app_bundle(
            repo_root=tmp_path,
            data_dir=tmp_path / "data",
            run_id="20260315T203138Z",
        )
        is True
    )
    assert captured["command"][:4] == [
        "open",
        "-na",
        str(tmp_path / "data" / ".ui_bundle" / "xn2s.app"),
        "--args",
    ]
    assert "--run-id" in captured["command"]


def test_relaunch_ui_from_app_bundle_skips_for_interactive_terminal(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr("xs2n.ui.macos.bundle.sys.platform", "darwin")
    monkeypatch.setattr("xs2n.ui.macos.bundle.sys.stdin", _FakeStream(True))
    monkeypatch.setattr("xs2n.ui.macos.bundle.sys.stdout", _FakeStream(False))
    monkeypatch.setattr("xs2n.ui.macos.bundle.sys.stderr", _FakeStream(False))
    monkeypatch.setattr(
        "xs2n.ui.macos.bundle.subprocess.Popen",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("should not relaunch from an interactive terminal")
        ),
    )

    assert (
        relaunch_ui_from_app_bundle(
            repo_root=tmp_path,
            data_dir=tmp_path / "data",
            run_id="20260315T203138Z",
        )
        is False
    )
