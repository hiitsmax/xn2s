from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

from xs2n.schemas.digest import Issue, IssueThread


@dataclass(slots=True)
class SavedDigestPreview:
    run_id: str
    digest_title: str
    issues: list[Issue]
    issue_threads: list[IssueThread]


def load_saved_digest_preview(*, run_dir: Path) -> SavedDigestPreview | None:
    issues_doc = _load_json(run_dir / "issues.json")
    issue_threads_doc = _load_json(run_dir / "issue_assignments.json")
    if not isinstance(issues_doc, list) or not isinstance(issue_threads_doc, list):
        return None

    issues = _load_models(issues_doc, Issue)
    issue_threads = _load_models(issue_threads_doc, IssueThread)
    if issues is None or issue_threads is None:
        return None

    run_doc = _load_json_dict(run_dir / "run.json") or {}
    run_id = str(run_doc.get("run_id") or run_dir.name)
    digest_title = str(
        run_doc.get("digest_title")
        or (issues[0].title if issues else "No issue digest produced")
    )
    return SavedDigestPreview(
        run_id=run_id,
        digest_title=digest_title,
        issues=issues,
        issue_threads=issue_threads,
    )


def find_saved_issue_thread(
    preview: SavedDigestPreview,
    *,
    thread_id: str,
) -> tuple[Issue | None, IssueThread | None]:
    thread_by_id = {thread.thread_id: thread for thread in preview.issue_threads}
    thread = thread_by_id.get(thread_id)
    if thread is None:
        return None, None

    for issue in preview.issues:
        if thread_id in issue.thread_ids:
            return issue, thread
    return None, thread


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


def _load_models(payload: list[Any], model_type) -> list[Any] | None:  # noqa: ANN001
    models: list[Any] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        try:
            models.append(model_type.model_validate(item))
        except Exception:
            return None
    return models
