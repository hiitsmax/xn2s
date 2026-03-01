from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from xs2n.profile.following import (
    AUTHENTICATED_ACCOUNT_SENTINEL,
    import_following_handles,
)


class _DummyPerson:
    def __init__(self, screen_name: str) -> None:
        self.screen_name = screen_name


class _DummyBatch(list):
    async def next(self):  # noqa: ANN201
        return _DummyBatch()


class _DummyUser:
    def __init__(self) -> None:
        self.screen_name = "mx"

    async def get_following(self, count: int):  # noqa: ANN201
        return _DummyBatch([_DummyPerson("alpha"), _DummyPerson("beta")])


class _DummyClient:
    def __init__(self, locale: str) -> None:
        self.locale = locale
        self.user_called = False
        self.by_name_calls: list[str] = []

    async def user(self) -> _DummyUser:
        self.user_called = True
        return _DummyUser()

    async def get_user_by_screen_name(self, screen_name: str) -> _DummyUser:
        self.by_name_calls.append(screen_name)
        return _DummyUser()


def test_import_following_handles_uses_authenticated_session_for_self(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client_holder: dict[str, _DummyClient] = {}

    def fake_client(locale: str) -> _DummyClient:
        client = _DummyClient(locale)
        client_holder["client"] = client
        return client

    async def fake_ensure_authenticated_client(**kwargs):  # noqa: ANN202
        return None

    monkeypatch.setattr("xs2n.profile.following.Client", fake_client)
    monkeypatch.setattr(
        "xs2n.profile.following.ensure_authenticated_client",
        fake_ensure_authenticated_client,
    )

    handles = asyncio.run(
        import_following_handles(
            account_screen_name=AUTHENTICATED_ACCOUNT_SENTINEL,
            cookies_file=Path("cookies.json"),
            limit=10,
            prompt_login=lambda *_: ("u", "e", "p"),
        )
    )

    client = client_holder["client"]
    assert client.user_called is True
    assert client.by_name_calls == []
    assert handles == ["alpha", "beta"]
