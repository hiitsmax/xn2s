from pathlib import Path
from typing import Any

import typer

import xs2n.storage.onboard_state as onboard_state_storage
from xs2n.profile.browser_cookies import (
    BrowserCookieCandidate,
    describe_cookie_candidate,
    discover_x_cookie_candidates,
    maybe_warn_keychain_prompt,
    resolve_screen_name_from_cookies,
    write_cookie_candidate,
)
from xs2n.profile.helpers import normalize_handle


def normalize_following_account(raw: str) -> str:
    normalized = normalize_handle(raw)
    if normalized is None:
        raise typer.BadParameter(
            "Provide a valid X handle (with or without @) or profile URL (x.com/<handle>)."
        )
    return normalized


def _choose_following_from_logged_in_profile() -> BrowserCookieCandidate | None:
    maybe_warn_keychain_prompt(echo=typer.echo)
    try:
        candidates = discover_x_cookie_candidates(resolve_profiles=False)
    except RuntimeError:
        return None

    if len(candidates) == 1:
        selected = candidates[0]
        typer.echo(
            "Found logged-in browser session: "
            f"{describe_cookie_candidate(selected)}. Using it."
        )
        return selected

    typer.echo("Found logged-in browser sessions:")
    manual_choice = len(candidates) + 1
    for index, candidate in enumerate(candidates, start=1):
        typer.echo(f"{index}. {describe_cookie_candidate(candidate)}")
    typer.echo(f"{manual_choice}. Enter a different handle manually")

    while True:
        raw_choice = typer.prompt("Select profile number", default="1")
        try:
            choice = int(raw_choice)
        except ValueError:
            typer.echo("Please enter a valid number.", err=True)
            continue

        if 1 <= choice <= len(candidates):
            return candidates[choice - 1]
        if choice == manual_choice:
            return None

        typer.echo("Choice out of range. Try again.", err=True)


def sanitize_cli_parameters(parameters: dict[str, Any]) -> None:
    if parameters["paste"] and parameters["from_following"]:
        raise typer.BadParameter("Use either --paste or --from-following, not both.")

    state_path = onboard_state_storage.resolve_onboard_state_path(parameters)
    state = onboard_state_storage.load_onboard_state(state_path)

    if parameters["from_following"]:
        parameters["from_following"] = normalize_following_account(
            str(parameters["from_following"])
        )
        onboard_state_storage.save_onboard_state(
            {
                "last_following": str(parameters["from_following"]),
                "last_mode": "following",
            },
            path=state_path,
        )

    if parameters["paste"]:
        onboard_state_storage.save_onboard_state(
            {**state, "last_mode": "paste"},
            path=state_path,
        )
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
        onboard_state_storage.save_onboard_state(
            {**state, "last_mode": "paste"},
            path=state_path,
        )
        return

    if choice in {"following", "f", "2"}:
        selected_candidate = _choose_following_from_logged_in_profile()
        if selected_candidate:
            cookies_file = parameters.get("cookies_file")
            if isinstance(cookies_file, Path):
                saved_path = write_cookie_candidate(selected_candidate, cookies_file)
                typer.echo(f"Saved browser cookies to {saved_path}.")

            resolved_screen_name = (
                selected_candidate.screen_name
                or resolve_screen_name_from_cookies(selected_candidate.cookies)
            )
            if resolved_screen_name:
                parameters["from_following"] = resolved_screen_name
                typer.echo(f"Using logged-in profile @{resolved_screen_name}.")
            else:
                remembered_profile = state.get("last_following")
                if remembered_profile:
                    parameters["from_following"] = remembered_profile
                    typer.echo(
                        "Could not auto-detect the profile handle from cookies. "
                        f"Using last saved profile @{remembered_profile}."
                    )
                else:
                    parameters["from_following"] = typer.prompt(
                        "X screen name (@, plain, or x.com URL)",
                    )
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

        parameters["from_following"] = normalize_following_account(
            str(parameters["from_following"])
        )
        onboard_state_storage.save_onboard_state(
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
