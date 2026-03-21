from __future__ import annotations

from pathlib import Path

import pytest
import typer
from twikit.errors import Forbidden, UserNotFound

from xs2n.cli.helpers import choose_cookie_candidate
from xs2n.cli.onboard import import_following_with_recovery
from xs2n.profile.browser_cookies import BrowserCookieCandidate


def _cloudflare_error() -> Forbidden:
    return Forbidden('status: 403, message: "Attention Required! | Cloudflare"')


def test_choose_cookie_candidate_returns_single_without_prompt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    candidate = BrowserCookieCandidate(
        browser_name="chrome",
        domain="x.com",
        cookies={"auth_token": "t", "ct0": "c"},
        screen_name="mx",
    )

    def fail_prompt(*args, **kwargs):  # noqa: ANN002, ANN003
        raise AssertionError("prompt should not be used for a single candidate")

    monkeypatch.setattr("typer.prompt", fail_prompt)

    selected = choose_cookie_candidate([candidate])

    assert selected is candidate


def test_choose_cookie_candidate_with_multiple_candidates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    candidates = [
        BrowserCookieCandidate(
            browser_name="chrome",
            domain="x.com",
            cookies={"auth_token": "t1", "ct0": "c1"},
            screen_name="first",
        ),
        BrowserCookieCandidate(
            browser_name="firefox",
            domain="x.com",
            cookies={"auth_token": "t2", "ct0": "c2"},
            screen_name="second",
        ),
    ]
    responses = iter(["nope", "3", "2"])

    monkeypatch.setattr("typer.prompt", lambda *args, **kwargs: next(responses))

    selected = choose_cookie_candidate(candidates)

    assert selected is candidates[1]


def test_import_following_with_recovery_bootstraps_local_cookies_before_first_attempt(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    bootstrap_calls = {"count": 0}

    def fake_bootstrap(cookies_file: Path) -> Path:
        bootstrap_calls["count"] += 1
        return cookies_file

    monkeypatch.setattr(
        "xs2n.cli.onboard.maybe_bootstrap_cookies_from_local_browser",
        fake_bootstrap,
    )
    monkeypatch.setattr(
        "xs2n.cli.onboard.run_import_following_handles",
        lambda **kwargs: ["alpha", "beta"],
    )

    handles = import_following_with_recovery(
        account="mx",
        cookies_file=tmp_path / "cookies.json",
        limit=50,
    )

    assert handles == ["alpha", "beta"]
    assert bootstrap_calls["count"] == 1


def test_import_following_with_recovery_retries_after_local_cookie_import(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    calls = {"count": 0}

    def fake_run_import_following_handles(**kwargs):
        calls["count"] += 1
        if calls["count"] == 1:
            raise _cloudflare_error()
        return ["alpha", "beta"]

    monkeypatch.setattr(
        "xs2n.cli.onboard.run_import_following_handles",
        fake_run_import_following_handles,
    )
    monkeypatch.setattr(
        "xs2n.cli.helpers.bootstrap_cookies_from_local_browser_with_choice",
        lambda cookies_file: cookies_file,
    )

    def fail_confirm(*args, **kwargs):  # noqa: ANN002, ANN003
        raise AssertionError("confirm should not be called when local cookies succeed")

    monkeypatch.setattr("typer.confirm", fail_confirm)
    monkeypatch.setattr(
        "xs2n.cli.helpers.bootstrap_cookies_via_browser",
        lambda cookies_file: cookies_file,
    )

    handles = import_following_with_recovery(
        account="mx",
        cookies_file=tmp_path / "cookies.json",
        limit=50,
    )

    assert handles == ["alpha", "beta"]
    assert calls["count"] == 2


def test_import_following_with_recovery_falls_back_to_browser_bootstrap(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    calls = {"count": 0}

    def fake_run_import_following_handles(**kwargs):
        calls["count"] += 1
        if calls["count"] == 1:
            raise _cloudflare_error()
        return ["alpha", "beta"]

    monkeypatch.setattr(
        "xs2n.cli.onboard.run_import_following_handles",
        fake_run_import_following_handles,
    )
    monkeypatch.setattr(
        "xs2n.cli.helpers.bootstrap_cookies_from_local_browser_with_choice",
        lambda cookies_file: (_ for _ in ()).throw(RuntimeError("no browser cookies")),
    )
    monkeypatch.setattr("typer.confirm", lambda *args, **kwargs: True)
    monkeypatch.setattr(
        "xs2n.cli.helpers.bootstrap_cookies_via_browser",
        lambda cookies_file: cookies_file,
    )

    handles = import_following_with_recovery(
        account="mx",
        cookies_file=tmp_path / "cookies.json",
        limit=50,
    )

    assert handles == ["alpha", "beta"]
    assert calls["count"] == 2


def test_import_following_with_recovery_retries_browser_after_local_retry_cloudflare(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    calls = {"count": 0}

    def fake_run_import_following_handles(**kwargs):
        calls["count"] += 1
        if calls["count"] < 3:
            raise _cloudflare_error()
        return ["alpha", "beta"]

    monkeypatch.setattr(
        "xs2n.cli.onboard.run_import_following_handles",
        fake_run_import_following_handles,
    )
    monkeypatch.setattr(
        "xs2n.cli.helpers.bootstrap_cookies_from_local_browser_with_choice",
        lambda cookies_file: cookies_file,
    )
    monkeypatch.setattr("typer.confirm", lambda *args, **kwargs: True)
    monkeypatch.setattr(
        "xs2n.cli.helpers.bootstrap_cookies_via_browser",
        lambda cookies_file: cookies_file,
    )

    handles = import_following_with_recovery(
        account="mx",
        cookies_file=tmp_path / "cookies.json",
        limit=50,
    )

    assert handles == ["alpha", "beta"]
    assert calls["count"] == 3


def test_import_following_with_recovery_exits_if_user_declines_bootstrap(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(
        "xs2n.cli.onboard.run_import_following_handles",
        lambda **kwargs: (_ for _ in ()).throw(_cloudflare_error()),
    )
    monkeypatch.setattr(
        "xs2n.cli.helpers.bootstrap_cookies_from_local_browser_with_choice",
        lambda cookies_file: (_ for _ in ()).throw(RuntimeError("no browser cookies")),
    )
    monkeypatch.setattr("typer.confirm", lambda *args, **kwargs: False)

    with pytest.raises(typer.Exit) as exit_error:
        import_following_with_recovery(
            account="mx",
            cookies_file=tmp_path / "cookies.json",
            limit=50,
        )

    assert exit_error.value.exit_code == 1


def test_import_following_with_recovery_recovers_from_missing_profile(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    calls: list[str] = []

    def fake_run_import_following_handles(**kwargs):
        calls.append(kwargs["account_screen_name"])
        if len(calls) == 1:
            raise UserNotFound("The user does not exist.")
        return ["alpha", "beta"]

    monkeypatch.setattr(
        "xs2n.cli.onboard.run_import_following_handles",
        fake_run_import_following_handles,
    )
    monkeypatch.setattr(
        "typer.prompt",
        lambda message, **kwargs: "https://x.com/VineyardSunset_",
    )

    handles = import_following_with_recovery(
        account="manual_user",
        cookies_file=tmp_path / "cookies.json",
        limit=50,
    )

    assert handles == ["alpha", "beta"]
    assert calls == ["manual_user", "vineyardsunset_"]
