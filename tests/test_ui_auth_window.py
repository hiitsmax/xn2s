from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from xs2n.ui.auth_window import AuthWindow
from xs2n.ui.theme import CLASSIC_DARK_THEME

try:
    from xs2n.schemas.auth import AuthDoctorResult, ProviderStatus, RunReadiness
except ImportError:
    @dataclass(slots=True)
    class ProviderStatus:
        status: str
        summary: str
        detail: str | None

    @dataclass(slots=True)
    class RunReadiness:
        digest_ready: bool
        latest_ready: bool

    @dataclass(slots=True)
    class AuthDoctorResult:
        codex: ProviderStatus
        x: ProviderStatus
        run_readiness: RunReadiness


class FakeValueWidget:
    def __init__(self, value: str = "") -> None:
        self._value = value

    def value(self, new_value: str | None = None) -> str:
        if new_value is None:
            return self._value
        self._value = new_value
        return self._value


def test_update_snapshot_writes_provider_statuses_and_cookie_path() -> None:
    window = object.__new__(AuthWindow)
    window.codex_status_output = FakeValueWidget()
    window.x_status_output = FakeValueWidget()
    window.x_cookies_path_output = FakeValueWidget()

    snapshot = AuthDoctorResult(
        codex=ProviderStatus(
            status="ready",
            summary="Codex credentials available.",
            detail="Source: codex_auth_file",
        ),
        x=ProviderStatus(
            status="missing",
            summary="Missing X session.",
            detail="cookies.json",
        ),
        run_readiness=RunReadiness(
            digest_ready=True,
            latest_ready=False,
        ),
    )

    AuthWindow.update_snapshot(
        window,
        snapshot=snapshot,
        cookies_file=Path("tmp/cookies.json"),
    )

    assert "Codex credentials available." in window.codex_status_output.value()
    assert "Missing X session." in window.x_status_output.value()
    assert window.x_cookies_path_output.value() == "tmp/cookies.json"


def test_action_buttons_dispatch_expected_actions() -> None:
    window = object.__new__(AuthWindow)
    actions: list[str] = []
    window.on_action_requested = lambda action: actions.append(action)

    AuthWindow._on_refresh_clicked(window)
    AuthWindow._on_codex_login_clicked(window)
    AuthWindow._on_codex_logout_clicked(window)
    AuthWindow._on_x_login_clicked(window)
    AuthWindow._on_x_reset_clicked(window)

    assert actions == [
        "refresh",
        "codex_login",
        "codex_logout",
        "x_login",
        "x_reset",
    ]


def test_apply_theme_updates_window_sections_and_buttons() -> None:
    class FakeThemeWidget:
        def __init__(self) -> None:
            self.color_value = None
            self.selection_color_value = None
            self.label_color_value = None
            self.text_color_value = None
            self.redraw_calls = 0

        def color(self, value):  # noqa: ANN001
            self.color_value = value

        def selection_color(self, value):  # noqa: ANN001
            self.selection_color_value = value

        def labelcolor(self, value):  # noqa: ANN001
            self.label_color_value = value

        def textcolor(self, value):  # noqa: ANN001
            self.text_color_value = value

        def redraw(self) -> None:
            self.redraw_calls += 1

    window = object.__new__(AuthWindow)
    window.window = FakeThemeWidget()
    window.codex_header = FakeThemeWidget()
    window.x_header = FakeThemeWidget()
    window.path_label = FakeThemeWidget()
    window.codex_status_output = FakeThemeWidget()
    window.x_status_output = FakeThemeWidget()
    window.x_cookies_path_output = FakeThemeWidget()
    window.action_buttons = [FakeThemeWidget(), FakeThemeWidget()]

    AuthWindow.apply_theme(window, CLASSIC_DARK_THEME)

    assert window.window.color_value is not None
    assert window.codex_header.color_value is not None
    assert window.x_header.color_value is not None
    assert window.codex_status_output.text_color_value is not None
    assert window.x_status_output.text_color_value is not None
    assert window.x_cookies_path_output.text_color_value is not None
    assert window.action_buttons[0].selection_color_value is not None
    assert window.window.redraw_calls == 1
