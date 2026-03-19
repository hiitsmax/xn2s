from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timezone

from xs2n.ui.artifacts import RUN_ROOT_PREFIX, RunRecord


RUN_LIST_WIDTH_PADDING = 18
DEFAULT_RUN_LIST_COLUMN_KEYS = ("started_at", "digest_title")


@dataclass(frozen=True, slots=True)
class RunListColumn:
    key: str
    label: str
    tooltip: str
    compact_width: int
    minimum_width: int
    preferred_width: int
    stretch_weight: int


RUN_LIST_COLUMNS = (
    RunListColumn(
        key="started_at",
        label="Date",
        tooltip="Run start time in UTC.",
        compact_width=84,
        minimum_width=96,
        preferred_width=108,
        stretch_weight=0,
    ),
    RunListColumn(
        key="digest_title",
        label="Digest",
        tooltip="Primary digest headline extracted from digest.md.",
        compact_width=144,
        minimum_width=220,
        preferred_width=360,
        stretch_weight=6,
    ),
    RunListColumn(
        key="root_name",
        label="Source",
        tooltip="Run root such as report_runs_last24h_limit100.",
        compact_width=72,
        minimum_width=92,
        preferred_width=108,
        stretch_weight=1,
    ),
    RunListColumn(
        key="status",
        label="Status",
        tooltip="Run status from run.json.",
        compact_width=62,
        minimum_width=76,
        preferred_width=88,
        stretch_weight=0,
    ),
    RunListColumn(
        key="model",
        label="Model",
        tooltip="Model used for the digest run.",
        compact_width=92,
        minimum_width=108,
        preferred_width=132,
        stretch_weight=1,
    ),
    RunListColumn(
        key="count_triplet",
        label="Counts",
        tooltip="Threads/kept/issues for the run.",
        compact_width=84,
        minimum_width=96,
        preferred_width=104,
        stretch_weight=0,
    ),
    RunListColumn(
        key="run_id",
        label="Run ID",
        tooltip="Timestamp-based run folder id.",
        compact_width=112,
        minimum_width=132,
        preferred_width=148,
        stretch_weight=1,
    ),
)

RUN_LIST_COLUMNS_BY_KEY = {column.key: column for column in RUN_LIST_COLUMNS}


def normalize_run_list_column_keys(column_keys: Sequence[str]) -> tuple[str, ...]:
    requested_keys = set(column_keys)
    normalized_keys = tuple(
        column.key
        for column in RUN_LIST_COLUMNS
        if column.key in requested_keys
    )
    return normalized_keys or DEFAULT_RUN_LIST_COLUMN_KEYS


def visible_run_list_columns(column_keys: Sequence[str]) -> list[RunListColumn]:
    normalized_keys = normalize_run_list_column_keys(column_keys)
    return [RUN_LIST_COLUMNS_BY_KEY[key] for key in normalized_keys]


def format_run_list_row(
    run: RunRecord,
    *,
    column_keys: Sequence[str],
) -> str:
    return "\t".join(
        _sanitize_run_list_text(_format_run_list_value(run, column.key))
        for column in visible_run_list_columns(column_keys)
    )


def compute_run_list_widths(
    total_width: int,
    *,
    column_keys: Sequence[str],
) -> tuple[int, ...]:
    columns = visible_run_list_columns(column_keys)
    if not columns:
        return ()

    available_width = max(80, total_width - RUN_LIST_WIDTH_PADDING)
    preferred_total = sum(column.preferred_width for column in columns)
    minimum_total = sum(column.minimum_width for column in columns)

    if available_width >= preferred_total:
        widths = [column.preferred_width for column in columns]
        _distribute_extra_width(
            widths,
            extra_width=available_width - preferred_total,
            columns=columns,
        )
        return tuple(widths)

    if available_width >= minimum_total and preferred_total > minimum_total:
        interpolation = (available_width - minimum_total) / (
            preferred_total - minimum_total
        )
        widths = [
            column.minimum_width
            + int(
                (column.preferred_width - column.minimum_width) * interpolation
            )
            for column in columns
        ]
        _distribute_extra_width(
            widths,
            extra_width=available_width - sum(widths),
            columns=columns,
        )
        return tuple(widths)

    widths = [
        max(
            column.compact_width,
            int(round((available_width * column.preferred_width) / preferred_total)),
        )
        for column in columns
    ]
    _remove_width(
        widths,
        width_to_remove=sum(widths) - available_width,
        columns=columns,
        minimum_widths=[column.compact_width for column in columns],
    )
    _remove_width(
        widths,
        width_to_remove=sum(widths) - available_width,
        columns=columns,
        minimum_widths=[1 for _ in columns],
    )
    _distribute_extra_width(
        widths,
        extra_width=available_width - sum(widths),
        columns=columns,
    )
    return tuple(widths)


def _format_run_list_value(run: RunRecord, column_key: str) -> str:
    if column_key == "started_at":
        return _format_run_started_label(run)
    if column_key == "digest_title":
        return run.digest_title or f"Run {run.run_id}"
    if column_key == "root_name":
        return _format_run_root_label(run.root_name)
    if column_key == "status":
        return _format_run_status_label(run.status)
    if column_key == "model":
        return run.model or "unknown"
    if column_key == "count_triplet":
        return _format_run_count_triplet(run)
    if column_key == "run_id":
        return run.run_id
    raise KeyError(f"Unsupported run-list column: {column_key}")


def _format_run_root_label(root_name: str) -> str:
    if root_name == RUN_ROOT_PREFIX:
        return "ALL"

    suffix = root_name.removeprefix(f"{RUN_ROOT_PREFIX}_")
    compact_label = (
        suffix.replace("last24h", "24h")
        .replace("limit", "")
        .replace("_", "/")
        .strip("/")
    )
    return (compact_label or root_name).upper()


def _format_run_started_label(run: RunRecord) -> str:
    started_at = _parse_datetime(run.started_at)
    if started_at is None:
        started_at = _parse_timestamp_from_run_id(run.run_id)
    if started_at is None:
        return run.run_id
    return started_at.astimezone(timezone.utc).strftime("%m-%d %H:%M")


def _format_run_status_label(status: str | None) -> str:
    normalized_status = (status or "unknown").lower()
    return {
        "completed": "Done",
        "running": "Running",
        "failed": "Failed",
        "cancelled": "Stopped",
        "canceled": "Stopped",
        "unknown": "Unknown",
    }.get(normalized_status, normalized_status.title())


def _format_run_count_triplet(run: RunRecord) -> str:
    return "/".join(
        [
            "-" if value is None else str(value)
            for value in (run.thread_count, run.kept_count, run.issue_count)
        ]
    )


def _sanitize_run_list_text(text: str) -> str:
    return " ".join(text.replace("\t", " ").splitlines()).strip()


def _distribute_extra_width(
    widths: list[int],
    *,
    extra_width: int,
    columns: Sequence[RunListColumn],
) -> None:
    if extra_width <= 0:
        return

    expand_order = _expand_indexes(columns)
    for index in range(extra_width):
        widths[expand_order[index % len(expand_order)]] += 1


def _remove_width(
    widths: list[int],
    *,
    width_to_remove: int,
    columns: Sequence[RunListColumn],
    minimum_widths: Sequence[int],
) -> None:
    if width_to_remove <= 0:
        return

    shrink_order = _shrink_indexes(columns)
    while width_to_remove > 0:
        removed_any_width = False
        for index in shrink_order:
            if width_to_remove <= 0:
                break
            if widths[index] <= minimum_widths[index]:
                continue
            widths[index] -= 1
            width_to_remove -= 1
            removed_any_width = True
        if not removed_any_width:
            break


def _expand_indexes(columns: Sequence[RunListColumn]) -> list[int]:
    indexes = [
        index
        for index, column in enumerate(columns)
        for _ in range(max(1, column.stretch_weight))
    ]
    return indexes or [len(columns) - 1]


def _shrink_indexes(columns: Sequence[RunListColumn]) -> list[int]:
    weighted_indexes = sorted(
        range(len(columns)),
        key=lambda index: (
            columns[index].stretch_weight,
            columns[index].preferred_width,
        ),
    )
    return weighted_indexes or [0]


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    normalized = value.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        return None


def _parse_timestamp_from_run_id(value: str) -> datetime | None:
    try:
        return datetime.strptime(value, "%Y%m%dT%H%M%SZ").replace(
            tzinfo=timezone.utc
        )
    except ValueError:
        return None
