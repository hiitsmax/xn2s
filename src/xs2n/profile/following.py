from __future__ import annotations

import asyncio
from pathlib import Path

from twikit import Client

from xs2n.profile.helpers import normalize_handle
from xs2n.profile.auth import LoginPrompt, ensure_authenticated_client

IMPORT_FOLLOWING_HANDLES_LIMIT = 2000
DEFAULT_IMPORT_FOLLOWING_HANDLES = 2000
AUTHENTICATED_ACCOUNT_SENTINEL = "__self__"


async def import_following_handles(
    account_screen_name: str,
    cookies_file: Path,
    limit: int,
    prompt_login: LoginPrompt,
) -> list[str]:
    client = Client("en-US")
    inferred_username = (
        None if account_screen_name == AUTHENTICATED_ACCOUNT_SENTINEL else account_screen_name
    )
    await ensure_authenticated_client(
        client=client,
        cookies_file=cookies_file,
        prompt=prompt_login,
        inferred_username=inferred_username,
    )

    if account_screen_name == AUTHENTICATED_ACCOUNT_SENTINEL:
        user = await client.user()
    else:
        user = await client.get_user_by_screen_name(account_screen_name)
    batch = await user.get_following(count=min(IMPORT_FOLLOWING_HANDLES_LIMIT, max(1, limit)))

    handles: list[str] = []
    seen: set[str] = set()
    while True:
        for person in batch:
            normalized = normalize_handle(person.screen_name)
            if normalized is None or normalized in seen:
                continue
            seen.add(normalized)
            handles.append(normalized)
            if len(handles) >= limit:
                return handles

        if len(batch) == 0 or len(handles) >= limit:
            break

        batch = await batch.next()
        if len(batch) == 0:
            break

    return handles

def run_import_following_handles(
    account_screen_name: str,
    cookies_file: Path,
    limit: int,
    prompt_login: LoginPrompt,
) -> list[str]:
    return asyncio.run(
        import_following_handles(
            account_screen_name=account_screen_name,
            cookies_file=cookies_file,
            limit=limit,
            prompt_login=prompt_login,
        )
    )
