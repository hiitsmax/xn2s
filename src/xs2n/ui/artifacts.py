from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
from typing import Any, Literal


DEFAULT_UI_DATA_PATH = Path("data")
RUN_ROOT_PREFIX = "report_runs"
PREFERRED_ARTIFACT_NAMES = [
    "digest.html",
    "digest.md",
    "run.json",
    "phases.json",
    "issues.json",
    "issue_assignments.json",
    "filtered_threads.json",
    "threads.json",
    "timeline_window.json",
    "llm_calls",
]
SECTION_BY_ARTIFACT_NAME = {
    "digest.html": ("◆", "Digest"),
    "digest.md": ("◆", "Digest"),
    "run.json": ("▣", "Run metadata"),
    "phases.json": ("↻", "Phase trace"),
    "issues.json": ("!", "Issues"),
    "issue_assignments.json": ("⇄", "Issue assignments"),
    "filtered_threads.json": ("◌", "Filtered threads"),
    "threads.json": ("☰", "Threads"),
    "timeline_window.json": ("◫", "Timeline window"),
    "llm_calls/": ("▸", "LLM calls"),
}
ArtifactKind = Literal["directory", "html", "json", "markdown", "text", "unknown"]
ArtifactRenderKind = Literal["html", "markdown", "text"]
DIRECTORY_PREVIEW_ENTRY_LIMIT = 200
TEXT_PREVIEW_BYTE_LIMIT = 64 * 1024
JSON_PRETTY_PRINT_BYTE_LIMIT = 64 * 1024


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


@dataclass(slots=True, frozen=True)
class ArtifactPreview:
    body: str
    render_kind: ArtifactRenderKind
    truncated: bool = False
    summary: str | None = None


@dataclass(slots=True)
class ArtifactSectionRecord:
    icon: str
    label: str
    artifact_name: str

    @property
    def browser_label(self) -> str:
        return f"{self.icon} {self.label}"


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
    digest_title: str | None = None
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

    for path in (run.artifact_paths or _list_run_entries(run.run_dir)):
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


def load_artifact_preview(artifact: ArtifactRecord) -> ArtifactPreview:
    path = artifact.path
    if not path.exists():
        return ArtifactPreview(
            body=f"Missing artifact: {path}\n",
            render_kind="text",
        )

    if path.is_dir():
        return _load_directory_preview(path)

    if artifact.kind == "json":
        return _load_json_preview(path)

    render_kind: ArtifactRenderKind = "text"
    if artifact.kind == "markdown":
        render_kind = "markdown"
    elif artifact.kind == "html":
        render_kind = "html"
    return _load_text_preview(path, render_kind=render_kind)


def list_artifact_sections(
    artifacts: list[ArtifactRecord],
) -> list[ArtifactSectionRecord]:
    sections = [
        ArtifactSectionRecord(
            icon=section_icon,
            label=section_label,
            artifact_name=artifact.name,
        )
        for artifact in artifacts
        if (
            section_definition := SECTION_BY_ARTIFACT_NAME.get(artifact.name)
        ) is not None
        for section_icon, section_label in [section_definition]
    ]
    if sections or not artifacts:
        return sections

    fallback_artifact = artifacts[0]
    return [
        ArtifactSectionRecord(
            icon="•",
            label=fallback_artifact.name.rstrip("/"),
            artifact_name=fallback_artifact.name,
        )
    ]


def load_artifact_text(path: Path) -> str:
    artifact = ArtifactRecord(
        name=path.name,
        path=path,
        kind=_artifact_kind(path) if path.exists() else "unknown",
        exists=path.exists(),
    )
    return load_artifact_preview(artifact).body


def delete_runs(runs: Sequence[RunRecord]) -> None:
    for run in runs:
        if not run.run_dir.exists():
            continue
        if not run.run_dir.is_dir():
            raise OSError(f"Run path is not a directory: {run.run_dir}")
        shutil.rmtree(run.run_dir)


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
    digest_path = _resolve_metadata_path(
        run_dir=run_dir,
        metadata_value=(
            metadata.get("primary_artifact_path")
            if metadata and metadata.get("primary_artifact_path")
            else metadata.get("digest_path") if metadata else None
        ),
        fallback_name="digest.html",
    )
    if digest_path is None:
        digest_path = _resolve_metadata_path(
            run_dir=run_dir,
            metadata_value=metadata.get("digest_path") if metadata else None,
            fallback_name="digest.md",
        )
    if metadata is None:
        return RunRecord(
            root_name=run_root.name,
            run_id=run_dir.name,
            run_dir=run_dir,
            status="unknown",
            digest_path=digest_path,
            digest_title=_extract_digest_title(
                digest_path,
                run_id=run_dir.name,
                status="unknown",
                stored_digest_title=None,
            ),
            artifact_paths=_list_run_entries(run_dir),
        )

    run_id = _optional_str(metadata.get("run_id")) or run_dir.name
    status = _optional_str(metadata.get("status"))

    return RunRecord(
        root_name=run_root.name,
        run_id=run_id,
        run_dir=run_dir,
        status=status,
        started_at=_optional_str(metadata.get("started_at")),
        finished_at=_optional_str(metadata.get("finished_at")),
        model=_optional_str(metadata.get("model")),
        timeline_file=_optional_str(metadata.get("timeline_file")),
        thread_count=_optional_int(metadata.get("thread_count")),
        kept_count=_optional_int(metadata.get("kept_count")),
        issue_count=_optional_int(metadata.get("issue_count")),
        digest_path=digest_path,
        digest_title=_extract_digest_title(
            digest_path,
            run_id=run_id,
            status=status,
            stored_digest_title=_optional_str(metadata.get("digest_title")),
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


def _load_directory_preview(path: Path) -> ArtifactPreview:
    entries = _visible_directory_entries(path)
    visible_entries = entries[:DIRECTORY_PREVIEW_ENTRY_LIMIT]
    lines = [f"{path.name}/", ""]
    lines.extend(visible_entries or ["(empty directory)"])

    hidden_count = len(entries) - len(visible_entries)
    summary = None
    if hidden_count > 0:
        summary = (
            "Truncated preview: "
            f"showing first {len(visible_entries)} of {len(entries)} entries."
        )
        lines.extend(
            [
                "",
                f"... {hidden_count} more entries omitted from the preview ...",
            ]
        )

    return ArtifactPreview(
        body="\n".join(lines) + "\n",
        render_kind="text",
        truncated=hidden_count > 0,
        summary=summary,
    )


def _load_json_preview(path: Path) -> ArtifactPreview:
    file_size = path.stat().st_size
    if file_size > JSON_PRETTY_PRINT_BYTE_LIMIT:
        return _load_truncated_text_preview(path, file_size=file_size)

    raw_text = path.read_text(encoding="utf-8", errors="replace")
    try:
        payload = json.loads(raw_text)
    except json.JSONDecodeError:
        return ArtifactPreview(body=raw_text, render_kind="text")

    return ArtifactPreview(
        body=f"{json.dumps(payload, ensure_ascii=False, indent=2)}\n",
        render_kind="text",
    )


def _load_text_preview(
    path: Path,
    *,
    render_kind: ArtifactRenderKind,
) -> ArtifactPreview:
    file_size = path.stat().st_size
    if file_size > TEXT_PREVIEW_BYTE_LIMIT:
        return _load_truncated_text_preview(path, file_size=file_size)

    return ArtifactPreview(
        body=path.read_text(encoding="utf-8", errors="replace"),
        render_kind=render_kind,
    )


def _load_truncated_text_preview(
    path: Path,
    *,
    file_size: int,
) -> ArtifactPreview:
    preview_text = _read_preview_text(
        path,
        byte_limit=TEXT_PREVIEW_BYTE_LIMIT,
    )
    if preview_text and not preview_text.endswith("\n"):
        preview_text = f"{preview_text}\n"
    preview_lines = [
        "Preview truncated.",
        f"File size: {file_size} bytes.",
        f"Showing first {TEXT_PREVIEW_BYTE_LIMIT} bytes only.",
        "",
        preview_text,
    ]
    return ArtifactPreview(
        body="\n".join(preview_lines),
        render_kind="text",
        truncated=True,
        summary=(
            "Truncated preview: "
            f"first {TEXT_PREVIEW_BYTE_LIMIT} bytes of {file_size} bytes."
        ),
    )


def _read_preview_text(path: Path, *, byte_limit: int) -> str:
    with path.open("rb") as handle:
        return handle.read(byte_limit).decode("utf-8", errors="replace")


def _visible_directory_entries(path: Path) -> list[str]:
    return [
        child.name
        for child in sorted(path.iterdir())
        if not child.name.startswith(".")
    ]


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
    if suffix == ".html":
        return "html"
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


def _extract_digest_title(
    path: Path | None,
    *,
    run_id: str,
    status: str | None,
    stored_digest_title: str | None,
) -> str:
    if stored_digest_title:
        return stored_digest_title
    if path is None or not path.exists() or path.is_dir():
        return _fallback_digest_title(run_id=run_id, status=status)

    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return _fallback_digest_title(run_id=run_id, status=status)

    issue_heading = _first_digest_heading(lines)
    if issue_heading is not None:
        return issue_heading

    top_issues_line = _first_top_issues_line(lines)
    if top_issues_line is not None:
        return top_issues_line

    return _fallback_digest_title(run_id=run_id, status=status)


def _first_digest_heading(lines: list[str]) -> str | None:
    for raw_line in lines[:80]:
        stripped_line = raw_line.strip()
        if not stripped_line.startswith("### "):
            continue
        normalized = _normalize_digest_title_text(stripped_line[4:])
        if normalized:
            return normalized
    return None


def _first_top_issues_line(lines: list[str]) -> str | None:
    inside_top_issues = False
    for raw_line in lines[:120]:
        stripped_line = raw_line.strip()
        if stripped_line == "## Top Issues":
            inside_top_issues = True
            continue
        if not inside_top_issues or not stripped_line:
            continue
        if stripped_line.startswith("## "):
            return None
        if stripped_line.startswith("_Generated "):
            continue
        normalized = _normalize_digest_title_text(stripped_line)
        if normalized:
            return normalized
    return None


def _normalize_digest_title_text(text: str) -> str:
    normalized = text.strip().strip("*_`")
    return normalized.rstrip(".")


def _fallback_digest_title(*, run_id: str, status: str | None) -> str:
    if status == "running":
        return "Digest in progress"
    return f"Run {run_id}"
