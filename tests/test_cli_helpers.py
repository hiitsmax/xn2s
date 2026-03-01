from __future__ import annotations

import pytest
import typer

from xs2n.cli.helpers import normalize_following_account, sanitize_cli_parameters


def test_sanitize_cli_parameters_rejects_missing_mode_without_wizard() -> None:
    parameters = {
        "paste": False,
        "from_following": None,
        "wizard": False,
    }

    with pytest.raises(typer.BadParameter):
        sanitize_cli_parameters(parameters)


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
