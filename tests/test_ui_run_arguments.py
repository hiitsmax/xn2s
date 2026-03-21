from __future__ import annotations

from pathlib import Path

import pytest

from xs2n.ui.run_arguments import (
    DEFAULT_COOKIES_PATH,
    IssuesRunArguments,
    LatestRunArguments,
    __all__ as run_arguments_exports,
)


def test_digest_run_arguments_use_defaults_for_blank_form_values() -> None:
    arguments = IssuesRunArguments.from_form(
        timeline_file="",
        output_dir="",
        model="",
    )

    assert arguments.to_cli_args() == [
        "report",
        "issues",
        "--timeline-file",
        "data/timeline.json",
        "--output-dir",
        "data/report_runs",
        "--model",
        "gpt-5.4-mini",
        "--jsonl-events",
    ]


def test_digest_run_arguments_reject_invalid_parallel_workers() -> None:
    arguments = IssuesRunArguments.from_form(
        timeline_file="data/timeline.json",
        output_dir="data/report_runs",
        model="gpt-5.4-mini",
    )

    assert arguments.model == "gpt-5.4-mini"


def test_ui_run_arguments_exports_only_honest_issue_surface() -> None:
    assert "DigestRunArguments" not in run_arguments_exports


def test_latest_run_arguments_omit_blank_optional_since() -> None:
    arguments = LatestRunArguments.from_form(
        since="   ",
        lookback_hours="24",
        cookies_file="",
        limit="",
        timeline_file="",
        sources_file="",
        home_latest=False,
        output_dir="",
        model="",
    )

    assert arguments.since is None
    assert arguments.cookies_file == DEFAULT_COOKIES_PATH
    assert "--since" not in arguments.to_cli_args()
    assert "--home-latest" not in arguments.to_cli_args()


def test_latest_run_arguments_include_since_and_home_latest() -> None:
    arguments = LatestRunArguments.from_form(
        since="2026-03-15T20:31:38Z",
        lookback_hours=12,
        cookies_file=Path("tmp/cookies.json"),
        limit=120,
        timeline_file=Path("tmp/timeline.json"),
        sources_file=Path("tmp/sources.json"),
        home_latest=True,
        output_dir=Path("tmp/report_runs"),
        model="gpt-5.5-mini",
    )

    assert arguments.to_cli_args() == [
        "report",
        "latest",
        "--lookback-hours",
        "12",
        "--cookies-file",
        "tmp/cookies.json",
        "--limit",
        "120",
        "--timeline-file",
        "tmp/timeline.json",
        "--sources-file",
        "tmp/sources.json",
        "--output-dir",
        "tmp/report_runs",
        "--model",
        "gpt-5.5-mini",
        "--jsonl-events",
        "--since",
        "2026-03-15T20:31:38Z",
        "--home-latest",
    ]


def test_latest_run_arguments_reject_invalid_lookback_hours() -> None:
    with pytest.raises(ValueError, match="Lookback hours must be a positive integer."):
        LatestRunArguments.from_form(
            since=None,
            lookback_hours="abc",
            cookies_file="cookies.json",
            limit="100",
            timeline_file="data/timeline.json",
            sources_file="data/sources.json",
            home_latest=False,
            output_dir="data/report_runs",
            model="gpt-5.4",
        )


def test_latest_run_arguments_build_following_refresh_command() -> None:
    arguments = LatestRunArguments(
        cookies_file=Path("tmp/cookies.json"),
        sources_file=Path("tmp/sources.json"),
    )

    assert arguments.to_following_refresh_command().args == [
        "onboard",
        "--refresh-following",
        "--cookies-file",
        "tmp/cookies.json",
        "--sources-file",
        "tmp/sources.json",
    ]
