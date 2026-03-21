from __future__ import annotations

import os
from pathlib import Path
import tempfile

from xs2n.schemas.report_schedule import ReportScheduleCatalog


DEFAULT_REPORT_SCHEDULES_PATH = Path("data/report_schedules.json")
_LATEST_ARGUMENT_KEYS = {
    "since",
    "lookback_hours",
    "cookies_file",
    "limit",
    "timeline_file",
    "sources_file",
    "home_latest",
    "output_dir",
    "model",
}


def load_report_schedules(path: Path | None = None) -> ReportScheduleCatalog:
    storage_path = path or DEFAULT_REPORT_SCHEDULES_PATH
    if not storage_path.exists():
        return ReportScheduleCatalog()

    try:
        return ReportScheduleCatalog.model_validate_json(
            storage_path.read_text(encoding="utf-8")
        )
    except ValueError as error:
        raise ValueError(
            f"Could not load report schedule catalog from {storage_path}: {error}"
        ) from error


def save_report_schedules(
    catalog: ReportScheduleCatalog,
    *,
    path: Path | None = None,
) -> None:
    storage_path = path or DEFAULT_REPORT_SCHEDULES_PATH
    storage_path.parent.mkdir(parents=True, exist_ok=True)
    compact_catalog = ReportScheduleCatalog(
        schedules=[
            schedule.model_copy(
                update={
                    "latest_arguments": {
                        key: value
                        for key, value in schedule.latest_arguments.items()
                        if key in _LATEST_ARGUMENT_KEYS
                    },
                    "last_run": None,
                }
            )
            for schedule in catalog.schedules
        ]
    )
    serialized_catalog = f"{compact_catalog.model_dump_json(indent=2)}\n"
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=storage_path.parent,
            prefix=f".{storage_path.name}.",
            suffix=".tmp",
            delete=False,
        ) as temp_file:
            temp_file.write(serialized_catalog)
            temp_file.flush()
            os.fsync(temp_file.fileno())
            temp_path = Path(temp_file.name)
        os.replace(temp_path, storage_path)
    finally:
        if temp_path is not None and temp_path.exists():
            temp_path.unlink(missing_ok=True)
