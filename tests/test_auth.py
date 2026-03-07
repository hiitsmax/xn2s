from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from xs2n.profile.auth import ensure_authenticated_client, prompt_login


def test_prompt_login_prefills_username_from_screen_name(monkeypatch: pytest.MonkeyPatch) -> None:
    prompt_calls: list[tuple[str, object, bool]] = []

    def fake_prompt(message: str, default: object = None, hide_input: bool = False):  # noqa: ANN001
        prompt_calls.append((message, default, hide_input))
        if message == "Email (or phone)":
            return "me@example.com"
        if message == "Username (without @)":
            return default
        return "secret"

    monkeypatch.setattr("typer.echo", lambda *args, **kwargs: None)
    monkeypatch.setattr("typer.prompt", fake_prompt)

    result = prompt_login(Path("cookies.json"), inferred_username="vineyardsunset_")

    assert result == ("me@example.com", "vineyardsunset_", "secret")
    assert ("Username (without @)", "vineyardsunset_", False) in prompt_calls


def test_ensure_authenticated_client_passes_inferred_username() -> None:
    class DummyClient:
        loaded: str | None = None
        login_payload: dict[str, str] | None = None

        def load_cookies(self, path: str) -> None:
            self.loaded = path

        async def login(
            self,
            auth_info_1: str,
            auth_info_2: str,
            password: str,
            cookies_file: str,
        ) -> None:
            self.login_payload = {
                "auth_info_1": auth_info_1,
                "auth_info_2": auth_info_2,
                "password": password,
                "cookies_file": cookies_file,
            }

    prompt_args: tuple[Path, str | None] | None = None

    def fake_prompt(cookies_file: Path, inferred_username: str | None) -> tuple[str, str, str]:
        nonlocal prompt_args
        prompt_args = (cookies_file, inferred_username)
        return ("me@example.com", inferred_username or "fallback", "secret")

    client = DummyClient()
    cookies_file = Path("missing-cookies.json")
    asyncio.run(
        ensure_authenticated_client(
            client=client,  # type: ignore[arg-type]
            cookies_file=cookies_file,
            prompt=fake_prompt,
            inferred_username="vineyardsunset_",
        )
    )

    assert prompt_args == (cookies_file, "vineyardsunset_")
    assert client.login_payload is not None
    assert client.login_payload["auth_info_2"] == "vineyardsunset_"
