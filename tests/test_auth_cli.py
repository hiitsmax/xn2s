from __future__ import annotations

import json
from pathlib import Path
import sys
from types import ModuleType

import pytest

from xs2n.cli.auth import doctor, x_login, x_reset
from xs2n.profile.playwright import bootstrap_cookies_via_browser
from xs2n.schemas.auth import AuthDoctorResult, ProviderStatus, RunReadiness


def test_auth_doctor_emits_json_snapshot(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    snapshot = AuthDoctorResult(
        codex=ProviderStatus(
            status="ready",
            summary="Codex credentials available.",
            detail="Source: codex_auth_file",
        ),
        x=ProviderStatus(
            status="missing",
            summary="X cookies file is missing required session cookies.",
            detail=str(tmp_path / "cookies.json"),
        ),
        run_readiness=RunReadiness(
            digest_ready=True,
            latest_ready=False,
        ),
    )
    monkeypatch.setattr(
        "xs2n.cli.auth.build_auth_doctor_result",
        lambda **kwargs: snapshot,
    )

    doctor(
        json_output=True,
        cookies_file=tmp_path / "cookies.json",
        codex_bin="codex",
    )

    payload = json.loads(capsys.readouterr().out)
    assert payload["codex"]["status"] == "ready"
    assert payload["x"]["status"] == "missing"
    assert payload["run_readiness"] == {
        "digest_ready": True,
        "latest_ready": False,
    }


def test_x_login_reports_saved_cookie_path(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    cookies_file = tmp_path / "cookies.json"
    monkeypatch.setattr(
        "xs2n.cli.auth.login_x_session",
        lambda **kwargs: cookies_file,
    )

    x_login(cookies_file=cookies_file)

    assert str(cookies_file) in capsys.readouterr().out


def test_x_reset_deletes_existing_cookie_file(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    cookies_file = tmp_path / "cookies.json"
    cookies_file.write_text("{}", encoding="utf-8")

    x_reset(cookies_file=cookies_file)

    assert not cookies_file.exists()
    assert "Removed X session cookies" in capsys.readouterr().out


def test_x_reset_is_idempotent_when_cookie_file_is_missing(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    cookies_file = tmp_path / "cookies.json"

    x_reset(cookies_file=cookies_file)

    assert not cookies_file.exists()
    assert "No X session cookies were stored" in capsys.readouterr().out


def test_bootstrap_cookies_via_browser_waits_for_required_cookies(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    events: dict[str, object] = {}

    class FakePage:
        def goto(self, url: str, wait_until: str) -> None:
            events["goto"] = (url, wait_until)

        def wait_for_timeout(self, timeout_ms: int) -> None:
            waits = events.setdefault("waits", [])
            assert isinstance(waits, list)
            waits.append(timeout_ms)

    class FakeContext:
        def __init__(self) -> None:
            self._calls = 0
            self._page = FakePage()

        def new_page(self) -> FakePage:
            return self._page

        def cookies(self, url: str) -> list[dict[str, str]]:
            events["cookies_url"] = url
            self._calls += 1
            if self._calls < 3:
                return [{"name": "guest_id", "value": "guest"}]
            return [
                {"name": "auth_token", "value": "token-value"},
                {"name": "ct0", "value": "csrf-value"},
            ]

    class FakeBrowser:
        def __init__(self) -> None:
            self.closed = False
            self.context = FakeContext()

        def new_context(self) -> FakeContext:
            return self.context

        def close(self) -> None:
            self.closed = True
            events["closed"] = True

    class FakeChromium:
        def launch(self, headless: bool) -> FakeBrowser:
            events["headless"] = headless
            browser = FakeBrowser()
            events["browser"] = browser
            return browser

    fake_playwright = ModuleType("playwright")
    fake_sync_api = ModuleType("playwright.sync_api")

    chromium = FakeChromium()

    class FakeManager:
        def __enter__(self):  # noqa: ANN204
            context = ModuleType("playwright_context")
            context.chromium = chromium
            return context

        def __exit__(self, exc_type, exc, tb) -> bool:  # noqa: ANN001, ANN201
            return False

    fake_sync_api.sync_playwright = lambda: FakeManager()
    fake_playwright.sync_api = fake_sync_api

    monkeypatch.setitem(sys.modules, "playwright", fake_playwright)
    monkeypatch.setitem(sys.modules, "playwright.sync_api", fake_sync_api)
    monkeypatch.setattr(
        "xs2n.profile.playwright.typer.prompt",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("interactive Enter prompt should not be used")
        ),
    )

    saved_path = bootstrap_cookies_via_browser(tmp_path / "cookies.json")

    assert saved_path == tmp_path / "cookies.json"
    assert json.loads(saved_path.read_text(encoding="utf-8")) == {
        "auth_token": "token-value",
        "ct0": "csrf-value",
    }
    assert events["goto"] == ("https://x.com/i/flow/login", "domcontentloaded")
    assert events["cookies_url"] == "https://x.com"
    assert events["waits"] == [1000, 1000]
    assert events["closed"] is True
