from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Literal


DEFAULT_UI_DATA_PATH = Path("data")
RUN_ROOT_PREFIX = "report_runs"
PREFERRED_ARTIFACT_NAMES = [
    "digest.md",
    "run.json",
    "phases.json",
    "taxonomy.json",
    "issues.json",
    "issue_assignments.json",
    "processed_threads.json",
    "filtered_threads.json",
    "categorized_threads.json",
    "threads.json",
    "llm_calls",
]
ArtifactKind = Literal["directory", "json", "markdown", "text", "unknown"]


@dataclass(slots=True)
class PhaseRecord:
    name: str
    status: str | None = None
    started_at: str | None = None
    finished_at: str | None = None
    duration_ms: int | None = None
    input_count: int | None = None
    output_count: int | None = None
    artifact_paths: list[str] = field(default_factory=list)
    counts: dict[str, int] = field(default_factory=dict)
    error_type: str | None = None
    error_message: str | None = None


@dataclass(slots=True)
class ArtifactRecord:
    name: str
    path: Path
    kind: ArtifactKind
    exists: bool
    phase_name: str | None = None


@dataclass(slots=True)
class RunRecord:
    root_name: str
    run_id: str
    run_dir: Path
    status: str | None = None
    started_at: str | None = None
    finished_at: str | None = None
    model: str | None = None
    timeline_file: str | None = None
    thread_count: int | None = None
    kept_count: int | None = None
    issue_count: int | None = None
    digest_path: Path | None = None
    phases_path: Path | None = None
    llm_calls_dir: Path | None = None
    artifact_paths: list[Path] = field(default_factory=list)


def scan_runs(data_dir: Path = DEFAULT_UI_DATA_PATH) -> list[RunRecord]:
    runs: list[RunRecord] = []
    for run_root in _iter_run_roots(data_dir):
        for candidate in sorted(run_root.iterdir(), reverse=True):
            if candidate.name.startswith(".") or not candidate.is_dir():
                continue
            runs.append(_build_run_record(run_root=run_root, run_dir=candidate))
    runs.sort(key=_run_sort_key, reverse=True)
    return runs


def load_phase_records(run: RunRecord) -> list[PhaseRecord]:
    phases_path = run.phases_path or run.run_dir / "phases.json"
    payload = _load_json(phases_path)
    if not isinstance(payload, list):
        return []

    phases: list[PhaseRecord] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        counts_doc = item.get("counts")
        counts: dict[str, int] = {}
        if isinstance(counts_doc, dict):
            counts = {
                str(key): int(value)
                for key, value in counts_doc.items()
                if isinstance(value, int)
            }
        artifact_paths_doc = item.get("artifact_paths")
        artifact_paths: list[str] = []
        if isinstance(artifact_paths_doc, list):
            artifact_paths = [
                path
                for path in artifact_paths_doc
                if isinstance(path, str)
            ]
        phases.append(
            PhaseRecord(
                name=str(item.get("name") or "unknown"),
                status=_optional_str(item.get("status")),
                started_at=_optional_str(item.get("started_at")),
                finished_at=_optional_str(item.get("finished_at")),
                duration_ms=_optional_int(item.get("duration_ms")),
                input_count=_optional_int(item.get("input_count")),
                output_count=_optional_int(item.get("output_count")),
                artifact_paths=artifact_paths,
                counts=counts,
                error_type=_optional_str(item.get("error_type")),
                error_message=_optional_str(item.get("error_message")),
            )
        )
    return phases


def list_run_artifacts(run: RunRecord) -> list[ArtifactRecord]:
    phase_by_name = _artifact_phase_map(run)
    records: list[ArtifactRecord] = []

    for path in _list_run_entries(run.run_dir):
        if path.is_dir():
            records.append(
                ArtifactRecord(
                    name=f"{path.name}/",
                    path=path,
                    kind="directory",
                    exists=True,
                    phase_name=phase_by_name.get(f"{path.name}/")
                    or phase_by_name.get(path.name),
                )
            )
            for child in sorted(path.iterdir()):
                if child.name.startswith(".") or child.is_dir():
                    continue
                relative_name = f"{path.name}/{child.name}"
                records.append(
                    ArtifactRecord(
                        name=relative_name,
                        path=child,
                        kind=_artifact_kind(child),
                        exists=True,
                        phase_name=phase_by_name.get(relative_name),
                    )
                )
            continue

        records.append(
            ArtifactRecord(
                name=path.name,
                path=path,
                kind=_artifact_kind(path),
                exists=True,
                phase_name=phase_by_name.get(path.name),
            )
        )

    return sorted(records, key=_artifact_sort_key)


def load_artifact_text(path: Path) -> str:
    if not path.exists():
        return f"Missing artifact: {path}\n"

    if path.is_dir():
        entries = [
            child.name
            for child in sorted(path.iterdir())
            if not child.name.startswith(".")
        ]
        lines = [f"{path.name}/", ""]
        lines.extend(entries or ["(empty directory)"])
        return "\n".join(lines) + "\n"

    raw_text = path.read_text(encoding="utf-8", errors="replace")
    if path.suffix.lower() != ".json":
        return raw_text

    try:
        payload = json.loads(raw_text)
    except json.JSONDecodeError:
        return raw_text
    return f"{json.dumps(payload, ensure_ascii=False, indent=2)}\n"


def format_run_summary(run: RunRecord) -> str:
    count_triplet = [
        "-" if value is None else str(value)
        for value in (run.thread_count, run.kept_count, run.issue_count)
    ]
    status = run.status or "unknown"
    model = run.model or "unknown-model"
    return (
        f"[{run.root_name}] {run.run_id} | {status} | {model} | "
        f"threads/kept/issues: {'/'.join(count_triplet)}"
    )


def format_run_details(run: RunRecord) -> str:
    lines = [
        f"run_id: {run.run_id}",
        f"root: {run.root_name}",
        f"status: {run.status or 'unknown'}",
        f"model: {run.model or 'unknown'}",
        f"started_at: {run.started_at or '-'}",
        f"finished_at: {run.finished_at or '-'}",
        f"timeline_file: {run.timeline_file or '-'}",
        f"thread_count: {_format_optional_int(run.thread_count)}",
        f"kept_count: {_format_optional_int(run.kept_count)}",
        f"issue_count: {_format_optional_int(run.issue_count)}",
    ]
    if run.digest_path is not None:
        lines.append(f"digest_path: {run.digest_path}")
    if run.phases_path is not None:
        lines.append(f"phases_path: {run.phases_path}")
    if run.llm_calls_dir is not None:
        lines.append(f"llm_calls_dir: {run.llm_calls_dir}")
    return "\n".join(lines)


def _iter_run_roots(data_dir: Path) -> list[Path]:
    if not data_dir.exists():
        return []
    return [
        candidate
        for candidate in sorted(data_dir.iterdir())
        if candidate.is_dir()
        and not candidate.name.startswith(".")
        and candidate.name.startswith(RUN_ROOT_PREFIX)
    ]


def _build_run_record(*, run_root: Path, run_dir: Path) -> RunRecord:
    metadata = _load_json_dict(run_dir / "run.json")
    if metadata is None:
        return RunRecord(
            root_name=run_root.name,
            run_id=run_dir.name,
            run_dir=run_dir,
            status="unknown",
            artifact_paths=_list_run_entries(run_dir),
        )

    return RunRecord(
        root_name=run_root.name,
        run_id=_optional_str(metadata.get("run_id")) or run_dir.name,
        run_dir=run_dir,
        status=_optional_str(metadata.get("status")),
        started_at=_optional_str(metadata.get("started_at")),
        finished_at=_optional_str(metadata.get("finished_at")),
        model=_optional_str(metadata.get("model")),
        timeline_file=_optional_str(metadata.get("timeline_file")),
        thread_count=_optional_int(metadata.get("thread_count")),
        kept_count=_optional_int(metadata.get("kept_count")),
        issue_count=_optional_int(metadata.get("issue_count")),
        digest_path=_resolve_metadata_path(
            run_dir=run_dir,
            metadata_value=metadata.get("digest_path"),
            fallback_name="digest.md",
        ),
        phases_path=_resolve_metadata_path(
            run_dir=run_dir,
            metadata_value=metadata.get("phases_path"),
            fallback_name="phases.json",
        ),
        llm_calls_dir=_resolve_metadata_path(
            run_dir=run_dir,
            metadata_value=metadata.get("llm_calls_dir"),
            fallback_name="llm_calls",
        ),
        artifact_paths=_list_run_entries(run_dir),
    )


def _load_json(path: Path) -> Any | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _load_json_dict(path: Path) -> dict[str, Any] | None:
    payload = _load_json(path)
    if isinstance(payload, dict):
        return payload
    return None


def _list_run_entries(run_dir: Path) -> list[Path]:
    if not run_dir.exists():
        return []
    return [
        candidate
        for candidate in sorted(run_dir.iterdir())
        if not candidate.name.startswith(".")
    ]


def _artifact_phase_map(run: RunRecord) -> dict[str, str]:
    artifact_phase: dict[str, str] = {}
    for phase in load_phase_records(run):
        for artifact_path in phase.artifact_paths:
            resolved_path = _resolve_phase_artifact_path(
                run_dir=run.run_dir,
                artifact_path=artifact_path,
            )
            candidates = {resolved_path.name}
            if resolved_path.parent == run.run_dir / "llm_calls":
                candidates.add(f"llm_calls/{resolved_path.name}")
            if resolved_path.is_dir():
                candidates.add(f"{resolved_path.name}/")
            for candidate in candidates:
                artifact_phase.setdefault(candidate, phase.name)
    return artifact_phase


def _resolve_phase_artifact_path(*, run_dir: Path, artifact_path: str) -> Path:
    candidate = Path(artifact_path)
    if candidate.is_absolute():
        return candidate
    if candidate.exists():
        return candidate
    return run_dir / candidate.name


def _resolve_metadata_path(
    *,
    run_dir: Path,
    metadata_value: Any,
    fallback_name: str,
) -> Path | None:
    if isinstance(metadata_value, str) and metadata_value:
        candidate = Path(metadata_value)
        if candidate.is_absolute():
            return candidate
        if candidate.exists():
            return candidate
        run_relative = run_dir / candidate.name
        if run_relative.exists():
            return run_relative
        return run_relative

    fallback = run_dir / fallback_name
    if fallback.exists():
        return fallback
    return None


def _artifact_kind(path: Path) -> ArtifactKind:
    if path.is_dir():
        return "directory"
    suffix = path.suffix.lower()
    if suffix == ".json":
        return "json"
    if suffix == ".md":
        return "markdown"
    if suffix in {".txt", ".log"}:
        return "text"
    return "unknown"


def _run_sort_key(run: RunRecord) -> tuple[datetime, str]:
    started_at = _parse_datetime(run.started_at)
    if started_at is not None:
        return started_at, run.run_id
    inferred = _parse_timestamp_from_run_id(run.run_id)
    if inferred is not None:
        return inferred, run.run_id
    return datetime.min.replace(tzinfo=timezone.utc), run.run_id


def _artifact_sort_key(record: ArtifactRecord) -> tuple[int, int, str]:
    parent_rank = 1 if "/" in record.name else 0
    normalized_name = record.name.rstrip("/")
    try:
        preferred_rank = PREFERRED_ARTIFACT_NAMES.index(normalized_name)
    except ValueError:
        preferred_rank = len(PREFERRED_ARTIFACT_NAMES)
    return parent_rank, preferred_rank, record.name


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


def _optional_str(value: Any) -> str | None:
    if isinstance(value, str) and value:
        return value
    return None


def _optional_int(value: Any) -> int | None:
    if isinstance(value, int):
        return value
    return None


def _format_optional_int(value: int | None) -> str:
    if value is None:
        return "-"
    return str(value)
