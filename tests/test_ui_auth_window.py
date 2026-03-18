from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from xs2n.ui.auth_window import AuthWindow

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
