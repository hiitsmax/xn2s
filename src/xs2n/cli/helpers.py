from typing import Any

import typer

from xs2n.profile.helpers import normalize_handle


def normalize_following_account(raw: str) -> str:
    normalized = normalize_handle(raw)
    if normalized is None:
        raise typer.BadParameter(
            "Provide a valid X handle (with or without @) or profile URL (x.com/<handle>)."
        )
    return normalized


def sanitize_cli_parameters(parameters: dict[str, Any]) -> None:
    if parameters["paste"] and parameters["from_following"]:
        raise typer.BadParameter("Use either --paste or --from-following, not both.")

    if parameters["from_following"]:
        parameters["from_following"] = normalize_following_account(str(parameters["from_following"]))

    if parameters["paste"] or parameters["from_following"]:
        return

    if not parameters.get("wizard", False):
        raise typer.BadParameter(
            "Choose a mode:\n"
            "  xs2n onboard --paste\n"
            "  xs2n onboard --from-following <screen_name>\n"
            "Tip: use --wizard for interactive mode."
        )

    choice = typer.prompt(
        "Onboarding mode [1: paste, 2: following]",
        default="1",
    ).strip().lower()
    if choice in {"paste", "p", "1"}:
        parameters["paste"] = True
        return

    if choice in {"following", "f", "2"}:
        parameters["from_following"] = typer.prompt(
            "X screen name (@, plain, or x.com URL)",
        )
        parameters["from_following"] = normalize_following_account(str(parameters["from_following"]))
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
