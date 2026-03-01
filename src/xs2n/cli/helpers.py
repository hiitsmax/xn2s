from pathlib import Path
from typing import Any

import typer
import yaml

from xs2n.profile.browser_cookies import (
    describe_cookie_candidate,
    discover_x_cookie_candidates,
    maybe_warn_keychain_prompt,
)
from xs2n.profile.helpers import normalize_handle

DEFAULT_ONBOARD_STATE_PATH = Path("data/onboard_state.yaml")


def _load_onboard_state(path: Path = DEFAULT_ONBOARD_STATE_PATH) -> dict[str, str]:
    if not path.exists():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return {}
    return {str(k): str(v) for k, v in data.items() if isinstance(v, (str, int, float))}


def _save_onboard_state(state: dict[str, str], path: Path = DEFAULT_ONBOARD_STATE_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(state, sort_keys=True), encoding="utf-8")


def _onboard_state_path(parameters: dict[str, Any]) -> Path:
    override = parameters.get("onboard_state_file")
    if isinstance(override, Path):
        return override
    return DEFAULT_ONBOARD_STATE_PATH


def normalize_following_account(raw: str) -> str:
    normalized = normalize_handle(raw)
    if normalized is None:
        raise typer.BadParameter(
            "Provide a valid X handle (with or without @) or profile URL (x.com/<handle>)."
        )
    return normalized


def _choose_following_from_logged_in_profile() -> str | None:
    maybe_warn_keychain_prompt(echo=typer.echo)
    try:
        candidates = discover_x_cookie_candidates(resolve_profiles=True)
    except RuntimeError:
        return None

    named_candidates = [candidate for candidate in candidates if candidate.screen_name]
    if not named_candidates:
        return None

    if len(named_candidates) == 1:
        selected = named_candidates[0]
        typer.echo(
            "Found logged-in browser profile: "
            f"{describe_cookie_candidate(selected)}. Using it."
        )
        return selected.screen_name

    typer.echo("Found logged-in browser profiles:")
    manual_choice = len(named_candidates) + 1
    for index, candidate in enumerate(named_candidates, start=1):
        typer.echo(f"{index}. {describe_cookie_candidate(candidate)}")
    typer.echo(f"{manual_choice}. Enter a different handle manually")

    while True:
        raw_choice = typer.prompt("Select profile number", default="1")
        try:
            choice = int(raw_choice)
        except ValueError:
            typer.echo("Please enter a valid number.", err=True)
            continue

        if 1 <= choice <= len(named_candidates):
            return named_candidates[choice - 1].screen_name
        if choice == manual_choice:
            return None

        typer.echo("Choice out of range. Try again.", err=True)


def sanitize_cli_parameters(parameters: dict[str, Any]) -> None:
    if parameters["paste"] and parameters["from_following"]:
        raise typer.BadParameter("Use either --paste or --from-following, not both.")

    state_path = _onboard_state_path(parameters)
    state = _load_onboard_state(state_path)

    if parameters["from_following"]:
        parameters["from_following"] = normalize_following_account(str(parameters["from_following"]))
        _save_onboard_state(
            {
                "last_following": str(parameters["from_following"]),
                "last_mode": "following",
            },
            path=state_path,
        )

    if parameters["paste"]:
        _save_onboard_state({**state, "last_mode": "paste"}, path=state_path)
        return

    if parameters["from_following"]:
        return

    default_mode = "2" if state.get("last_mode") == "following" else "1"
    choice = typer.prompt(
        "Onboarding mode [1: paste, 2: following]",
        default=default_mode,
    ).strip().lower()
    if choice in {"paste", "p", "1"}:
        parameters["paste"] = True
        _save_onboard_state({**state, "last_mode": "paste"}, path=state_path)
        return

    if choice in {"following", "f", "2"}:
        selected_profile = _choose_following_from_logged_in_profile()
        if selected_profile:
            parameters["from_following"] = selected_profile
        else:
            prompt_default = state.get("last_following")
            if prompt_default:
                parameters["from_following"] = typer.prompt(
                    "X screen name (@, plain, or x.com URL)",
                    default=prompt_default,
                )
            else:
                parameters["from_following"] = typer.prompt(
                    "X screen name (@, plain, or x.com URL)",
                )

        parameters["from_following"] = normalize_following_account(str(parameters["from_following"]))
        _save_onboard_state(
            {
                "last_following": str(parameters["from_following"]),
                "last_mode": "following",
            },
            path=state_path,
        )
        return

    raise typer.BadParameter("Mode must be one of: 1, 2, paste, following.")


def collect_multiline_paste() -> str:
    typer.echo("Paste handles or profile URLs. Press Enter on an empty line to finish.")
    lines: list[str] = []
    while True:
        try:
            line = input()
        except EOFError:
            break
        if line.strip() == "":
            if lines:
                break
            continue
        lines.append(line)
    return "\n".join(lines)
