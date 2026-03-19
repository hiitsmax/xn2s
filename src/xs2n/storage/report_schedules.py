from __future__ import annotations

from pathlib import Path

from xs2n.schemas.report_schedule import ReportScheduleCatalog


DEFAULT_REPORT_SCHEDULES_PATH = Path("data/report_schedules.json")


def load_report_schedules(path: Path | None = None) -> ReportScheduleCatalog:
    storage_path = path or DEFAULT_REPORT_SCHEDULES_PATH
    if not storage_path.exists():
        return ReportScheduleCatalog()

    try:
        return ReportScheduleCatalog.model_validate_json(
            storage_path.read_text(encoding="utf-8")
        )
    except ValueError:
        return ReportScheduleCatalog()


def save_report_schedules(
    catalog: ReportScheduleCatalog,
    *,
    path: Path | None = None,
) -> None:
    storage_path = path or DEFAULT_REPORT_SCHEDULES_PATH
    storage_path.parent.mkdir(parents=True, exist_ok=True)
    storage_path.write_text(
        f"{catalog.model_dump_json(indent=2)}\n",
        encoding="utf-8",
    )
