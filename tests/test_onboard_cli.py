from __future__ import annotations

from pathlib import Path

import pytest
import typer

from xs2n.cli.onboard import onboard
from xs2n.profile.following import (
    AUTHENTICATED_ACCOUNT_SENTINEL,
    DEFAULT_IMPORT_FOLLOWING_HANDLES,
)
from xs2n.profile.types import OnboardResult


def test_onboard_refresh_following_replaces_sources_for_authenticated_account(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    import_calls: list[dict[str, object]] = []
    replaced: list[dict[str, object]] = []
    echoes: list[tuple[str, bool]] = []

    def fail_prompt(*args, **kwargs):  # noqa: ANN002, ANN003
        raise AssertionError("prompt should not be used for refresh shortcut")

    def fake_import_following_with_recovery(
        account: str,
        cookies_file: Path,
        limit: int,
    ) -> list[str]:
        import_calls.append(
            {
                "account": account,
                "cookies_file": cookies_file,
                "limit": limit,
            }
        )
        return ["alpha", "beta"]

    def fake_replace_profiles(entries, path: Path):  # noqa: ANN001
        replaced.append({"entries": entries, "path": path})
        return OnboardResult(added=2, skipped_duplicates=0, invalid=[])

    def fail_merge_profiles(*args, **kwargs):  # noqa: ANN002, ANN003
        raise AssertionError("merge should not be used for refresh shortcut")

    monkeypatch.setattr("typer.prompt", fail_prompt)
    monkeypatch.setattr(
        "xs2n.cli.onboard.import_following_with_recovery",
        fake_import_following_with_recovery,
    )
    monkeypatch.setattr("xs2n.cli.onboard.replace_profiles", fake_replace_profiles)
    monkeypatch.setattr("xs2n.cli.onboard.merge_profiles", fail_merge_profiles)
    monkeypatch.setattr(
        "typer.echo",
        lambda message, err=False: echoes.append((message, err)),
    )

    onboard(
        paste=False,
        from_following=None,
        wizard=False,
        refresh_following=True,
        cookies_file=tmp_path / "cookies.json",
        limit=DEFAULT_IMPORT_FOLLOWING_HANDLES,
        sources_file=tmp_path / "sources.json",
    )

    assert import_calls == [
        {
            "account": AUTHENTICATED_ACCOUNT_SENTINEL,
            "cookies_file": tmp_path / "cookies.json",
            "limit": DEFAULT_IMPORT_FOLLOWING_HANDLES,
        }
    ]
    assert replaced[0]["path"] == tmp_path / "sources.json"
    assert [entry.handle for entry in replaced[0]["entries"]] == ["alpha", "beta"]
    assert all(
        entry.added_via == "following_refresh" for entry in replaced[0]["entries"]
    )
    assert echoes == [
        ("Refreshed source catalog from the authenticated account's following list.", False),
        ("Stored 2 profiles in the sources catalog.", False),
    ]


def test_onboard_refresh_following_allows_empty_following_result(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    replaced: list[dict[str, object]] = []
    echoes: list[tuple[str, bool]] = []

    def fail_prompt(*args, **kwargs):  # noqa: ANN002, ANN003
        raise AssertionError("prompt should not be used for refresh shortcut")

    def fake_replace_profiles(entries, path: Path):  # noqa: ANN001
        replaced.append({"entries": entries, "path": path})
        return OnboardResult(added=0, skipped_duplicates=0, invalid=[])

    monkeypatch.setattr("typer.prompt", fail_prompt)
    monkeypatch.setattr(
        "xs2n.cli.onboard.import_following_with_recovery",
        lambda account, cookies_file, limit: [],
    )
    monkeypatch.setattr("xs2n.cli.onboard.replace_profiles", fake_replace_profiles)
    monkeypatch.setattr(
        "xs2n.cli.onboard.merge_profiles",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("merge should not be used for refresh shortcut")
        ),
    )
    monkeypatch.setattr(
        "typer.echo",
        lambda message, err=False: echoes.append((message, err)),
    )

    onboard(
        paste=False,
        from_following=None,
        wizard=False,
        refresh_following=True,
        cookies_file=tmp_path / "cookies.json",
        limit=DEFAULT_IMPORT_FOLLOWING_HANDLES,
        sources_file=tmp_path / "sources.json",
    )

    assert replaced[0]["path"] == tmp_path / "sources.json"
    assert replaced[0]["entries"] == []
    assert echoes == [
        ("Refreshed source catalog from the authenticated account's following list.", False),
        ("Stored 0 profiles in the sources catalog.", False),
    ]


def test_onboard_rejects_dead_wizard_flag(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(
        "xs2n.cli.onboard.process_paste_parameters",
        lambda parameters: (OnboardResult(added=0, skipped_duplicates=0, invalid=[]), []),
    )

    with pytest.raises(typer.BadParameter, match="--wizard"):
        onboard(
            paste=True,
            from_following=None,
            wizard=True,
            refresh_following=False,
            cookies_file=tmp_path / "cookies.json",
            limit=DEFAULT_IMPORT_FOLLOWING_HANDLES,
            sources_file=tmp_path / "sources.json",
        )
