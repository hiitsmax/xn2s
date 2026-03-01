from __future__ import annotations

from pathlib import Path
from typing import Callable

import typer
from twikit import Client

LoginPrompt = Callable[[Path, str | None], tuple[str, str, str]]


def prompt_login(cookies_file: Path, inferred_username: str | None = None) -> tuple[str, str, str]:
    cookies_path = cookies_file.resolve()
    typer.echo(
        "Hint: no Twikit cookies file found at "
        f"'{cookies_path}'. This command cannot read browser login cookies. "
        "Log in once here to create it for future runs."
    )
    auth_info_1 = typer.prompt("Email (or phone)")
    if inferred_username:
        auth_info_2 = typer.prompt("Username (without @)", default=inferred_username)
    else:
        auth_info_2 = typer.prompt("Username (without @)")
    password = typer.prompt("Password", hide_input=True)
    return auth_info_1, auth_info_2, password


async def ensure_authenticated_client(
    client: Client,
    cookies_file: Path,
    prompt: LoginPrompt,
    inferred_username: str | None = None,
) -> None:
    if cookies_file.exists():
        client.load_cookies(str(cookies_file))
        return

    auth_info_1, auth_info_2, password = prompt(cookies_file, inferred_username)
    await client.login(
        auth_info_1=auth_info_1,
        auth_info_2=auth_info_2,
        password=password,
        cookies_file=str(cookies_file),
    )


def is_cloudflare_block_error(error: Exception) -> bool:
    text = str(error).lower()
    if "status: 403" not in text:
        return False
    markers = (
        "cloudflare",
        "attention required",
        "you have been blocked",
        "unable to access x.com",
    )
    return any(marker in text for marker in markers)
