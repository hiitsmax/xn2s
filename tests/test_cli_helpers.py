from __future__ import annotations

from pathlib import Path

import pytest
import typer
import yaml

from xs2n.cli.helpers import normalize_following_account, sanitize_cli_parameters
from xs2n.profile.browser_cookies import BrowserCookieCandidate


@pytest.fixture(autouse=True)
def isolate_onboard_state_path(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr("xs2n.cli.helpers.DEFAULT_ONBOARD_STATE_PATH", tmp_path / "onboard_state.yaml")


def test_sanitize_cli_parameters_defaults_to_interactive_wizard(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("typer.prompt", lambda *args, **kwargs: "1")
    parameters = {
        "paste": False,
        "from_following": None,
        "wizard": False,
    }

    sanitize_cli_parameters(parameters)

    assert parameters["paste"] is True


def test_sanitize_cli_parameters_normalizes_following_handle_with_at_prefix() -> None:
    parameters = {
        "paste": False,
        "from_following": "@mx",
        "wizard": False,
    }

    sanitize_cli_parameters(parameters)

    assert parameters["from_following"] == "mx"


def test_sanitize_cli_parameters_normalizes_following_handle_from_url() -> None:
    parameters = {
        "paste": False,
        "from_following": "https://x.com/mx",
        "wizard": False,
    }

    sanitize_cli_parameters(parameters)

    assert parameters["from_following"] == "mx"


def test_sanitize_cli_parameters_wizard_allows_paste(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("typer.prompt", lambda *args, **kwargs: "1")
    parameters = {
        "paste": False,
        "from_following": None,
        "wizard": True,
    }

    sanitize_cli_parameters(parameters)

    assert parameters["paste"] is True


def test_sanitize_cli_parameters_wizard_requests_handle(monkeypatch: pytest.MonkeyPatch) -> None:
    answers = iter(["2", "https://x.com/mx"])
    monkeypatch.setattr("typer.prompt", lambda *args, **kwargs: next(answers))
    monkeypatch.setattr(
        "xs2n.cli.helpers.discover_x_cookie_candidates",
        lambda resolve_profiles=True: (_ for _ in ()).throw(RuntimeError("no cookies")),
    )
    parameters = {
        "paste": False,
        "from_following": None,
        "wizard": True,
    }

    sanitize_cli_parameters(parameters)

    assert parameters["from_following"] == "mx"


def test_normalize_following_account_rejects_invalid_input() -> None:
    with pytest.raises(typer.BadParameter):
        normalize_following_account("https://x.com/")


def test_sanitize_cli_parameters_uses_last_mode_as_prompt_default(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    state_file = tmp_path / "onboard_state.yaml"
    state_file.write_text("last_mode: following\nlast_following: mx\n", encoding="utf-8")
    prompts: list[tuple[str, dict[str, object]]] = []

    def fake_prompt(message: str, **kwargs: object) -> str:
        prompts.append((message, kwargs))
        return "1"

    monkeypatch.setattr("typer.prompt", fake_prompt)
    parameters = {
        "paste": False,
        "from_following": None,
        "wizard": False,
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
    state_file = tmp_path / "onboard_state.yaml"
    state_file.write_text("last_mode: following\nlast_following: mx\n", encoding="utf-8")
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
        "wizard": False,
        "onboard_state_file": state_file,
    }

    sanitize_cli_parameters(parameters)

    assert parameters["from_following"] == "mx"
    assert prompts[1][0] == "X screen name (@, plain, or x.com URL)"
    assert prompts[1][1]["default"] == "mx"


def test_sanitize_cli_parameters_persists_following_input(tmp_path: Path) -> None:
    state_file = tmp_path / "onboard_state.yaml"
    parameters = {
        "paste": False,
        "from_following": "@Neo",
        "wizard": False,
        "onboard_state_file": state_file,
    }

    sanitize_cli_parameters(parameters)

    saved_state = yaml.safe_load(state_file.read_text(encoding="utf-8"))
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
        "wizard": False,
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
        "wizard": False,
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
        "wizard": False,
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
    state_file = tmp_path / "onboard_state.yaml"
    parameters = {
        "paste": False,
        "from_following": None,
        "wizard": False,
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
    state_file = tmp_path / "onboard_state.yaml"
    state_file.write_text("last_mode: following\nlast_following: VineyardSunset_\n", encoding="utf-8")
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
        "wizard": False,
        "cookies_file": cookies_file,
        "onboard_state_file": state_file,
    }

    sanitize_cli_parameters(parameters)

    assert parameters["from_following"] == "vineyardsunset_"
    assert cookies_file.exists()
    assert prompts == ["Onboarding mode [1: paste, 2: following]"]
