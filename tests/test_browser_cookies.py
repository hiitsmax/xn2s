from __future__ import annotations

from pathlib import Path

import pytest

from xs2n.profile.browser_cookies import (
    BrowserCookieCandidate,
    bootstrap_cookies_from_local_browser,
    discover_x_cookie_candidates,
    load_x_cookies_from_installed_browser,
)


class DummyCookie:
    def __init__(self, name: str, value: str) -> None:
        self.name = name
        self.value = value


def test_discover_x_cookie_candidates_returns_required_cookies(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_loader(domain_name: str):  # noqa: ANN202
        if domain_name == "x.com":
            return [
                DummyCookie("auth_token", "token-value"),
                DummyCookie("ct0", "csrf-value"),
                DummyCookie("lang", "en"),
            ]
        return []

    monkeypatch.setattr(
        "xs2n.profile.browser_cookies._iter_cookie_loaders",
        lambda: [("chrome", fake_loader)],
    )
    monkeypatch.setattr(
        "xs2n.profile.browser_cookies._resolve_screen_name_from_cookies",
        lambda cookies: "mx",
    )

    candidates = discover_x_cookie_candidates()

    assert len(candidates) == 1
    assert candidates[0].cookies["auth_token"] == "token-value"
    assert candidates[0].cookies["ct0"] == "csrf-value"
    assert candidates[0].screen_name == "mx"


def test_discover_x_cookie_candidates_raises_if_missing_required(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_loader(domain_name: str):  # noqa: ANN202
        return [DummyCookie("lang", "en")]

    monkeypatch.setattr(
        "xs2n.profile.browser_cookies._iter_cookie_loaders",
        lambda: [("chrome", fake_loader)],
    )

    with pytest.raises(RuntimeError) as error:
        discover_x_cookie_candidates()

    assert "Could not find a logged-in X session" in str(error.value)


def test_load_x_cookies_from_installed_browser_returns_first_candidate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "xs2n.profile.browser_cookies.discover_x_cookie_candidates",
        lambda resolve_profiles=False: [
            BrowserCookieCandidate(
                browser_name="chrome",
                domain="x.com",
                cookies={"auth_token": "token-value", "ct0": "csrf-value"},
                screen_name=None,
            )
        ],
    )

    cookies = load_x_cookies_from_installed_browser()

    assert cookies["auth_token"] == "token-value"
    assert cookies["ct0"] == "csrf-value"


def test_bootstrap_cookies_from_local_browser_writes_file(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(
        "xs2n.profile.browser_cookies.discover_x_cookie_candidates",
        lambda resolve_profiles=False: [
            BrowserCookieCandidate(
                browser_name="chrome",
                domain="x.com",
                cookies={"auth_token": "token-value", "ct0": "csrf-value"},
                screen_name=None,
            )
        ],
    )
    path = tmp_path / "cookies.json"

    saved = bootstrap_cookies_from_local_browser(path)

    assert saved == path.resolve()
    assert '"auth_token": "token-value"' in path.read_text(encoding="utf-8")
