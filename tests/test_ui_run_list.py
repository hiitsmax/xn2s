from __future__ import annotations

from pathlib import Path

from xs2n.ui.artifacts import RunRecord
from xs2n.ui.run_list import (
    DEFAULT_RUN_LIST_COLUMN_KEYS,
    compute_run_list_widths,
    format_run_list_row,
    normalize_run_list_column_keys,
    visible_run_list_columns,
)


def test_format_run_list_row_defaults_to_date_and_digest() -> None:
    run = RunRecord(
        root_name="report_runs_last24h_limit100",
        run_id="20260315T203138Z",
        run_dir=Path("data/report_runs_last24h_limit100/20260315T203138Z"),
        started_at="2026-03-15T20:31:38+00:00",
        digest_title="Debate over whether interest or discipline matters more in mastering a skill",
        status="completed",
        model="gpt-5.4",
        thread_count=100,
        kept_count=12,
        issue_count=6,
    )

    assert format_run_list_row(
        run,
        column_keys=DEFAULT_RUN_LIST_COLUMN_KEYS,
    ).split("\t") == [
        "03-15 20:31",
        "Debate over whether interest or discipline matters more in mastering a skill",
    ]


def test_normalize_run_list_column_keys_falls_back_to_default() -> None:
    assert normalize_run_list_column_keys(()) == DEFAULT_RUN_LIST_COLUMN_KEYS
    assert normalize_run_list_column_keys(("unknown",)) == (
        DEFAULT_RUN_LIST_COLUMN_KEYS
    )
    assert [column.label for column in visible_run_list_columns(("run_id", "status"))] == [
        "Status",
        "Run ID",
    ]


def test_compute_run_list_widths_gives_extra_room_to_digest_column() -> None:
    narrow_widths = compute_run_list_widths(
        280,
        column_keys=("started_at", "digest_title", "status"),
    )
    wide_widths = compute_run_list_widths(
        560,
        column_keys=("started_at", "digest_title", "status"),
    )

    assert len(narrow_widths) == 3
    assert len(wide_widths) == 3
    assert wide_widths[1] > narrow_widths[1]
    assert wide_widths[1] > wide_widths[0]
    assert sum(wide_widths) > sum(narrow_widths)
