from __future__ import annotations

from types import SimpleNamespace

import xs2n.ui.app as app
from xs2n.ui.run_arguments import RunCommand


def test_refresh_following_click_uses_preferences_window_command() -> None:
    browser = object.__new__(app.ArtifactBrowserWindow)
    captured: list[RunCommand] = []
    command = RunCommand(
        label="refresh following sources",
        args=["onboard", "--refresh-following"],
    )
    browser.preferences_window = SimpleNamespace(
        current_following_refresh_command=lambda: command
    )
    browser._start_run_command = lambda received: captured.append(received)

    app.ArtifactBrowserWindow._on_refresh_following_clicked(browser)

    assert captured == [command]
