from __future__ import annotations

import json
from pathlib import Path

import pytest

import xs2n.utils.auth.openai_client as oauth_auth_module
import xs2n.utils.auth.openai_client as oauth_module


def test_build_openai_responses_model_uses_codex_oauth_credentials(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: dict[str, object] = {}

    class FakeAsyncOpenAI:
        def __init__(self, *, api_key: str, base_url: str) -> None:
            calls["async_client"] = {
                "api_key": api_key,
                "base_url": base_url,
            }

    class FakeModel:
        def __init__(
            self,
            model: str,
            openai_client: object,
            *,
            model_is_explicit: bool = True,
        ) -> None:
            self.openai_client = openai_client
            calls["model"] = {
                "model": model,
                "openai_client": openai_client,
                "model_is_explicit": model_is_explicit,
            }

    monkeypatch.setattr(
        oauth_module,
        "resolve_codex_oauth_credentials",
        lambda **_: oauth_module.CodexOAuthCredentials(
            token="oauth-token",
            base_url="https://chatgpt.com/backend-api/codex",
            source="codex_auth_file",
            account_id="account-123",
        ),
    )
    monkeypatch.setattr(oauth_module, "AsyncOpenAI", FakeAsyncOpenAI, raising=False)
    monkeypatch.setattr(
        oauth_module,
        "OpenAIResponsesModel",
        FakeModel,
        raising=False,
    )

    result = oauth_module.build_openai_responses_model(model="gpt-5.4-mini")

    assert calls["async_client"] == {
        "api_key": "oauth-token",
        "base_url": "https://chatgpt.com/backend-api/codex",
    }
    assert calls["model"] == {
        "model": "gpt-5.4-mini",
        "openai_client": result.openai_client,
        "model_is_explicit": True,
    }


def test_build_openai_responses_model_prefers_codex_oauth_over_openai_api_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: dict[str, object] = {}

    class FakeAsyncOpenAI:
        def __init__(self, *, api_key: str, base_url: str) -> None:
            calls["async_client"] = {
                "api_key": api_key,
                "base_url": base_url,
            }

    class FakeModel:
        def __init__(
            self,
            model: str,
            openai_client: object,
            *,
            model_is_explicit: bool = True,
        ) -> None:
            self.openai_client = openai_client
            calls["model"] = {
                "model": model,
                "openai_client": openai_client,
                "model_is_explicit": model_is_explicit,
            }

    monkeypatch.setenv("OPENAI_API_KEY", "openai-api-key")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    monkeypatch.setattr(
        oauth_module,
        "resolve_codex_oauth_credentials",
        lambda **_: oauth_module.CodexOAuthCredentials(
            token="oauth-token",
            base_url="https://chatgpt.com/backend-api/codex",
            source="codex_auth_file",
            account_id="account-123",
        ),
    )
    monkeypatch.setattr(oauth_module, "AsyncOpenAI", FakeAsyncOpenAI, raising=False)
    monkeypatch.setattr(
        oauth_module,
        "OpenAIResponsesModel",
        FakeModel,
        raising=False,
    )

    result = oauth_module.build_openai_responses_model(model="gpt-5.4-mini")

    assert calls["async_client"] == {
        "api_key": "oauth-token",
        "base_url": "https://chatgpt.com/backend-api/codex",
    }
    assert calls["model"] == {
        "model": "gpt-5.4-mini",
        "openai_client": result.openai_client,
        "model_is_explicit": True,
    }


def test_resolve_codex_oauth_credentials_refreshes_expiring_auth_file(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    codex_home = tmp_path / ".codex"
    codex_home.mkdir()
    auth_path = codex_home / "auth.json"
    auth_path.write_text(
        json.dumps(
            {
                "auth_mode": "chatgpt",
                "tokens": {
                    "access_token": "header.eyJleHAiOjF9.signature",
                    "refresh_token": "refresh-token",
                    "account_id": "account-123",
                },
            }
        ),
        encoding="utf-8",
    )

    def fake_refresh_auth_file(*, auth_path: Path, auth_doc: dict[str, object]) -> dict[str, object]:
        assert auth_path == codex_home / "auth.json"
        assert auth_doc["tokens"]["refresh_token"] == "refresh-token"
        return {
            "auth_mode": "chatgpt",
            "tokens": {
                "access_token": "fresh-access-token",
                "refresh_token": "fresh-refresh-token",
                "account_id": "account-123",
            },
        }

    monkeypatch.setenv("CODEX_HOME", str(codex_home))
    monkeypatch.setattr(oauth_auth_module, "_refresh_auth_file", fake_refresh_auth_file)
    monkeypatch.setattr(
        oauth_auth_module,
        "_token_is_expiring_soon",
        lambda access_token, *, refresh_leeway_seconds: True,
    )

    credentials = oauth_auth_module.resolve_codex_oauth_credentials()

    assert credentials.token == "fresh-access-token"
    assert credentials.base_url == "https://chatgpt.com/backend-api/codex"
    assert credentials.source == "codex_auth_file"
    assert credentials.account_id == "account-123"
