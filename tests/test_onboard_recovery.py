from __future__ import annotations

from pathlib import Path

import pytest
import typer
from twikit.errors import Forbidden

from xs2n.cli.onboard import import_following_with_recovery


def _cloudflare_error() -> Forbidden:
    return Forbidden('status: 403, message: "Attention Required! | Cloudflare"')


def test_import_following_with_recovery_retries_after_local_cookie_import(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    calls = {"count": 0}

    def fake_run_import_following_handles(**kwargs):
        calls["count"] += 1
        if calls["count"] == 1:
            raise _cloudflare_error()
        return ["alpha", "beta"]

    monkeypatch.setattr(
        "xs2n.cli.onboard.run_import_following_handles",
        fake_run_import_following_handles,
    )
    monkeypatch.setattr(
        "xs2n.cli.onboard.bootstrap_cookies_from_local_browser",
        lambda cookies_file: cookies_file,
    )

    def fail_confirm(*args, **kwargs):  # noqa: ANN002, ANN003
        raise AssertionError("confirm should not be called when local cookies succeed")

    monkeypatch.setattr("typer.confirm", fail_confirm)
    monkeypatch.setattr(
        "xs2n.cli.onboard.bootstrap_cookies_via_browser",
        lambda cookies_file: cookies_file,
    )

    handles = import_following_with_recovery(
        account="mx",
        cookies_file=tmp_path / "cookies.json",
        limit=50,
    )

    assert handles == ["alpha", "beta"]
    assert calls["count"] == 2


def test_import_following_with_recovery_falls_back_to_browser_bootstrap(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    calls = {"count": 0}

    def fake_run_import_following_handles(**kwargs):
        calls["count"] += 1
        if calls["count"] == 1:
            raise _cloudflare_error()
        return ["alpha", "beta"]

    monkeypatch.setattr(
        "xs2n.cli.onboard.run_import_following_handles",
        fake_run_import_following_handles,
    )
    monkeypatch.setattr(
        "xs2n.cli.onboard.bootstrap_cookies_from_local_browser",
        lambda cookies_file: (_ for _ in ()).throw(RuntimeError("no browser cookies")),
    )
    monkeypatch.setattr("typer.confirm", lambda *args, **kwargs: True)
    monkeypatch.setattr(
        "xs2n.cli.onboard.bootstrap_cookies_via_browser",
        lambda cookies_file: cookies_file,
    )

    handles = import_following_with_recovery(
        account="mx",
        cookies_file=tmp_path / "cookies.json",
        limit=50,
    )

    assert handles == ["alpha", "beta"]
    assert calls["count"] == 2


def test_import_following_with_recovery_exits_if_user_declines_bootstrap(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(
        "xs2n.cli.onboard.run_import_following_handles",
        lambda **kwargs: (_ for _ in ()).throw(_cloudflare_error()),
    )
    monkeypatch.setattr(
        "xs2n.cli.onboard.bootstrap_cookies_from_local_browser",
        lambda cookies_file: (_ for _ in ()).throw(RuntimeError("no browser cookies")),
    )
    monkeypatch.setattr("typer.confirm", lambda *args, **kwargs: False)

    with pytest.raises(typer.Exit) as exit_error:
        import_following_with_recovery(
            account="mx",
            cookies_file=tmp_path / "cookies.json",
            limit=50,
        )

    assert exit_error.value.exit_code == 1
