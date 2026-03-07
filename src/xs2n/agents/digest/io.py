from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ValidationError

from xs2n.storage import load_report_state, load_timeline, save_report_state

from .config import DEFAULT_TAXONOMY_DOC
from .models import SignalUnit, TaxonomyConfig, ThreadState, TimelineRecord


def to_jsonable(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, list):
        return [to_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {key: to_jsonable(item) for key, item in value.items()}
    return value


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"{json.dumps(to_jsonable(payload), ensure_ascii=False, indent=2)}\n",
        encoding="utf-8",
    )


def load_taxonomy(path: Path) -> TaxonomyConfig:
    if path.exists():
        return TaxonomyConfig.model_validate_json(path.read_text(encoding="utf-8"))
    return TaxonomyConfig.model_validate(DEFAULT_TAXONOMY_DOC)


def load_timeline_records(path: Path) -> list[TimelineRecord]:
    doc = load_timeline(path)
    raw_entries = doc.get("entries", [])
    if not isinstance(raw_entries, list):
        return []

    records: list[TimelineRecord] = []
    for item in raw_entries:
        if not isinstance(item, dict):
            continue
        try:
            records.append(TimelineRecord.model_validate(item))
        except ValidationError:
            continue
    records.sort(key=lambda record: record.created_at, reverse=True)
    return records


def load_previous_threads(path: Path) -> tuple[dict[str, Any], dict[str, ThreadState], datetime | None]:
    state_doc = load_report_state(path)
    raw_threads = state_doc.get("threads", {})
    previous_threads: dict[str, ThreadState] = {}
    if isinstance(raw_threads, dict):
        for conversation_id, raw_value in raw_threads.items():
            if not isinstance(conversation_id, str) or not isinstance(raw_value, dict):
                continue
            try:
                previous_threads[conversation_id] = ThreadState.model_validate(raw_value)
            except ValidationError:
                continue

    last_run_at = None
    raw_last_run_at = state_doc.get("last_run_at")
    if isinstance(raw_last_run_at, str):
        try:
            last_run_at = datetime.fromisoformat(raw_last_run_at)
        except ValueError:
            last_run_at = None

    return state_doc, previous_threads, last_run_at


def resolve_fresh_cutoff(
    *,
    now: datetime,
    last_run_at: datetime | None,
    window_minutes: int,
) -> datetime:
    if last_run_at is not None and last_run_at <= now:
        return last_run_at
    return now - timedelta(minutes=max(1, window_minutes))


def save_next_state(
    *,
    previous_doc: dict[str, Any],
    signals: list[SignalUnit],
    run_started_at: datetime,
    state_path: Path,
) -> None:
    next_threads = previous_doc.get("threads", {})
    if not isinstance(next_threads, dict):
        next_threads = {}

    for unit in signals:
        next_threads[unit.conversation_id] = ThreadState(
            title=unit.title,
            heat_status=unit.heat_status,
            momentum=unit.momentum,
            virality_score=unit.virality_score,
            disagreement_present=unit.disagreement_present,
            last_seen_at=run_started_at,
            source_urls=unit.source_urls,
        ).model_dump(mode="json")

    save_report_state(
        {
            "last_run_at": run_started_at.isoformat(),
            "threads": next_threads,
        },
        state_path,
    )
