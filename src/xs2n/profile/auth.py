from __future__ import annotations

from pathlib import Path
from typing import Callable

import typer
from twikit import Client

LoginPrompt = Callable[[Path], tuple[str, str, str]]


def prompt_login(cookies_file: Path) -> tuple[str, str, str]:
    cookies_path = cookies_file.resolve()
    typer.echo(
        "No Twikit cookies file found at "
        f"'{cookies_path}'. This command does not read your browser login cookies. "
        "Logging in once here will create the file for next runs."
    )
    auth_info_1 = typer.prompt("Auth info 1 (username/email/phone)")
    auth_info_2 = typer.prompt("Auth info 2 (email/username)")
    password = typer.prompt("Password", hide_input=True)
    return auth_info_1, auth_info_2, password


async def ensure_authenticated_client(
    client: Client,
    cookies_file: Path,
    prompt: LoginPrompt,
) -> None:
    if cookies_file.exists():
        client.load_cookies(str(cookies_file))
        return

    auth_info_1, auth_info_2, password = prompt(cookies_file)
    await client.login(
        auth_info_1=auth_info_1,
        auth_info_2=auth_info_2,
        password=password,
        cookies_file=str(cookies_file),
    )
