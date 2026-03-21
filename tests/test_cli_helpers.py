from __future__ import annotations

import json
from pathlib import Path

import pytest
import typer
from twikit.errors import Forbidden

from xs2n.cli.helpers import (
    normalize_following_account,
    retry_after_cloudflare_block,
    sanitize_cli_parameters,
)
from xs2n.profile.browser_cookies import BrowserCookieCandidate


@pytest.fixture(autouse=True)
def isolate_onboard_state_path(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(
        "xs2n.cli.helpers.onboard_state_storage.DEFAULT_ONBOARD_STATE_PATH",
        tmp_path / "onboard_state.json",
    )


def test_sanitize_cli_parameters_defaults_to_interactive_prompt(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("typer.prompt", lambda *args, **kwargs: "1")
    parameters = {
        "paste": False,
        "from_following": None,
    }

    sanitize_cli_parameters(parameters)

    assert parameters["paste"] is True


def test_sanitize_cli_parameters_normalizes_following_handle_with_at_prefix() -> None:
    parameters = {
        "paste": False,
        "from_following": "@mx",
    }

    sanitize_cli_parameters(parameters)

    assert parameters["from_following"] == "mx"


def test_sanitize_cli_parameters_normalizes_following_handle_from_url() -> None:
    parameters = {
        "paste": False,
        "from_following": "https://x.com/mx",
    }

    sanitize_cli_parameters(parameters)

    assert parameters["from_following"] == "mx"


def test_sanitize_cli_parameters_requests_handle_for_following_choice(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    answers = iter(["2", "https://x.com/mx"])
    monkeypatch.setattr("typer.prompt", lambda *args, **kwargs: next(answers))
    monkeypatch.setattr(
        "xs2n.cli.helpers.discover_x_cookie_candidates",
        lambda resolve_profiles=True: (_ for _ in ()).throw(RuntimeError("no cookies")),
    )
    parameters = {
        "paste": False,
        "from_following": None,
    }

    sanitize_cli_parameters(parameters)

    assert parameters["from_following"] == "mx"


def test_sanitize_cli_parameters_refresh_following_skips_prompt_and_sets_mode(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    state_file = tmp_path / "onboard_state.json"

    def fail_prompt(*args, **kwargs):  # noqa: ANN002, ANN003
        raise AssertionError("prompt should not be used for refresh shortcut")

    monkeypatch.setattr("typer.prompt", fail_prompt)
    parameters = {
        "paste": False,
        "from_following": None,
        "refresh_following": True,
        "onboard_state_file": state_file,
    }

    sanitize_cli_parameters(parameters)

    saved_state = json.loads(state_file.read_text(encoding="utf-8"))
    assert saved_state == {"last_mode": "following"}


def test_normalize_following_account_rejects_invalid_input() -> None:
    with pytest.raises(typer.BadParameter):
        normalize_following_account("https://x.com/")


def test_sanitize_cli_parameters_uses_last_mode_as_prompt_default(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    state_file = tmp_path / "onboard_state.json"
    state_file.write_text('{"last_mode": "following", "last_following": "mx"}', encoding="utf-8")
    prompts: list[tuple[str, dict[str, object]]] = []

    def fake_prompt(message: str, **kwargs: object) -> str:
        prompts.append((message, kwargs))
        return "1"

    monkeypatch.setattr("typer.prompt", fake_prompt)
    parameters = {
        "paste": False,
        "from_following": None,
        "onboard_state_file": state_file,
    }

    sanitize_cli_parameters(parameters)

    assert parameters["paste"] is True
    assert prompts[0][0] == "Onboarding mode [1: paste, 2: following]"
    assert prompts[0][1]["default"] == "2"


def test_sanitize_cli_parameters_uses_last_following_as_prompt_default(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    state_file = tmp_path / "onboard_state.json"
    state_file.write_text('{"last_mode": "following", "last_following": "mx"}', encoding="utf-8")
    prompts: list[tuple[str, dict[str, object]]] = []
    answers = iter(["2", "mx"])

    def fake_prompt(message: str, **kwargs: object) -> str:
        prompts.append((message, kwargs))
        return next(answers)

    monkeypatch.setattr("typer.prompt", fake_prompt)
    monkeypatch.setattr(
        "xs2n.cli.helpers.discover_x_cookie_candidates",
        lambda resolve_profiles=True: (_ for _ in ()).throw(RuntimeError("no cookies")),
    )
    parameters = {
        "paste": False,
        "from_following": None,
        "onboard_state_file": state_file,
    }

    sanitize_cli_parameters(parameters)

    assert parameters["from_following"] == "mx"
    assert prompts[1][0] == "X screen name (@, plain, or x.com URL)"
    assert prompts[1][1]["default"] == "mx"


def test_sanitize_cli_parameters_persists_following_input(tmp_path: Path) -> None:
    state_file = tmp_path / "onboard_state.json"
    parameters = {
        "paste": False,
        "from_following": "@Neo",
        "onboard_state_file": state_file,
    }

    sanitize_cli_parameters(parameters)

    saved_state = json.loads(state_file.read_text(encoding="utf-8"))
    assert parameters["from_following"] == "neo"
    assert saved_state == {"last_following": "neo", "last_mode": "following"}


def test_sanitize_cli_parameters_prefers_single_logged_in_profile(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("typer.prompt", lambda *args, **kwargs: "2")
    monkeypatch.setattr(
        "xs2n.cli.helpers.discover_x_cookie_candidates",
        lambda resolve_profiles=True: [
            BrowserCookieCandidate(
                browser_name="chrome",
                domain="x.com",
                cookies={"auth_token": "a", "ct0": "b"},
                screen_name="mx",
            )
        ],
    )
    parameters = {
        "paste": False,
        "from_following": None,
    }

    sanitize_cli_parameters(parameters)

    assert parameters["from_following"] == "mx"


def test_sanitize_cli_parameters_allows_choosing_among_logged_in_profiles(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    prompts: list[str] = []
    answers = iter(["2", "2"])

    def fake_prompt(message: str, **kwargs: object) -> str:
        prompts.append(message)
        return next(answers)

    monkeypatch.setattr("typer.prompt", fake_prompt)
    monkeypatch.setattr(
        "xs2n.cli.helpers.discover_x_cookie_candidates",
        lambda resolve_profiles=True: [
            BrowserCookieCandidate(
                browser_name="chrome",
                domain="x.com",
                cookies={"auth_token": "a", "ct0": "b"},
                screen_name="first",
            ),
            BrowserCookieCandidate(
                browser_name="firefox",
                domain="x.com",
                cookies={"auth_token": "c", "ct0": "d"},
                screen_name="second",
            ),
        ],
    )
    parameters = {
        "paste": False,
        "from_following": None,
    }

    sanitize_cli_parameters(parameters)

    assert parameters["from_following"] == "second"
    assert prompts == [
        "Onboarding mode [1: paste, 2: following]",
        "Select profile number",
    ]


def test_sanitize_cli_parameters_falls_back_to_manual_when_requested(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    answers = iter(["2", "3", "https://x.com/manual_user"])
    monkeypatch.setattr("typer.prompt", lambda *args, **kwargs: next(answers))
    monkeypatch.setattr(
        "xs2n.cli.helpers.discover_x_cookie_candidates",
        lambda resolve_profiles=True: [
            BrowserCookieCandidate(
                browser_name="chrome",
                domain="x.com",
                cookies={"auth_token": "a", "ct0": "b"},
                screen_name="auto",
            ),
            BrowserCookieCandidate(
                browser_name="firefox",
                domain="x.com",
                cookies={"auth_token": "c", "ct0": "d"},
                screen_name="backup",
            )
        ],
    )
    parameters = {
        "paste": False,
        "from_following": None,
    }

    sanitize_cli_parameters(parameters)

    assert parameters["from_following"] == "manual_user"


def test_sanitize_cli_parameters_uses_authenticated_session_when_handle_is_unknown(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    prompts: list[str] = []
    answers = iter(["2", "https://x.com/manual_user"])

    def fake_prompt(message: str, **kwargs: object) -> str:
        prompts.append(message)
        return next(answers)

    monkeypatch.setattr(
        "typer.prompt",
        fake_prompt,
    )
    monkeypatch.setattr(
        "xs2n.cli.helpers.discover_x_cookie_candidates",
        lambda resolve_profiles=True: [
            BrowserCookieCandidate(
                browser_name="chrome",
                domain="x.com",
                cookies={"auth_token": "a", "ct0": "b"},
                screen_name=None,
            )
        ],
    )
    monkeypatch.setattr(
        "xs2n.cli.helpers.resolve_screen_name_from_cookies",
        lambda cookies: None,
    )
    cookies_file = tmp_path / "cookies.json"
    state_file = tmp_path / "onboard_state.json"
    parameters = {
        "paste": False,
        "from_following": None,
        "cookies_file": cookies_file,
        "onboard_state_file": state_file,
    }

    sanitize_cli_parameters(parameters)

    assert parameters["from_following"] == "manual_user"
    assert cookies_file.exists()
    assert prompts == [
        "Onboarding mode [1: paste, 2: following]",
        "X screen name (@, plain, or x.com URL)",
    ]


def test_sanitize_cli_parameters_uses_last_saved_handle_when_cookie_profile_is_unknown(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    state_file = tmp_path / "onboard_state.json"
    state_file.write_text(
        '{"last_mode": "following", "last_following": "VineyardSunset_"}',
        encoding="utf-8",
    )
    prompts: list[str] = []

    def fake_prompt(message: str, **kwargs: object) -> str:
        prompts.append(message)
        return "2"

    monkeypatch.setattr("typer.prompt", fake_prompt)
    monkeypatch.setattr(
        "xs2n.cli.helpers.discover_x_cookie_candidates",
        lambda resolve_profiles=True: [
            BrowserCookieCandidate(
                browser_name="chrome",
                domain="x.com",
                cookies={"auth_token": "a", "ct0": "b"},
                screen_name=None,
            )
        ],
    )
    monkeypatch.setattr(
        "xs2n.cli.helpers.resolve_screen_name_from_cookies",
        lambda cookies: None,
    )
    cookies_file = tmp_path / "cookies.json"
    parameters = {
        "paste": False,
        "from_following": None,
        "cookies_file": cookies_file,
        "onboard_state_file": state_file,
    }

    sanitize_cli_parameters(parameters)

    assert parameters["from_following"] == "vineyardsunset_"
    assert cookies_file.exists()
    assert prompts == ["Onboarding mode [1: paste, 2: following]"]


def test_retry_after_cloudflare_block_uses_local_browser_before_browser_login(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    retry_calls = {"count": 0}

    def retry_operation() -> str:
        retry_calls["count"] += 1
        return "ok"

    def fail_confirm(*args, **kwargs):  # noqa: ANN002, ANN003
        raise AssertionError("confirm should not be called when local browser cookies work")

    monkeypatch.setattr(
        "xs2n.cli.helpers.bootstrap_cookies_from_local_browser_with_choice",
        lambda cookies_file: cookies_file,
    )
    monkeypatch.setattr("typer.confirm", fail_confirm)

    result = retry_after_cloudflare_block(
        retry_operation=retry_operation,
        cookies_file=tmp_path / "cookies.json",
        cloudflare_error=Forbidden('status: 403, message: "Attention Required! | Cloudflare"'),
    )

    assert result == "ok"
    assert retry_calls["count"] == 1
