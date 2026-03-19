from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from xs2n.ui.artifacts import (
    ArtifactRecord,
    delete_runs,
    list_artifact_sections,
    list_run_artifacts,
    load_artifact_preview,
    load_artifact_text,
    load_phase_records,
    scan_runs,
)


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"{json.dumps(payload, ensure_ascii=False, indent=2)}\n",
        encoding="utf-8",
    )


def test_scan_runs_discovers_multiple_roots_and_sorts_newest_first(
    tmp_path: Path,
) -> None:
    data_dir = tmp_path / "data"

    partial_run = data_dir / "report_runs" / "20260307T173044Z"
    partial_run.mkdir(parents=True)
    (partial_run / "threads.json").write_text("[]\n", encoding="utf-8")

    legacy_run = data_dir / "report_runs_fake" / "20260307T171055Z"
    _write_json(
        legacy_run / "run.json",
        {
            "run_id": "20260307T171055Z",
            "model": "gpt-4.1-mini",
            "thread_count": 5,
            "kept_count": 1,
            "issue_count": 1,
            "digest_path": str(legacy_run / "digest.md"),
        },
    )
    (legacy_run / "digest.md").write_text(
        (
            "# xs2n Digest Issue 20260307T171055Z\n\n"
            "## Top Issues\n\n"
            "No high-signal issues were produced in this run.\n"
        ),
        encoding="utf-8",
    )

    traced_run = data_dir / "report_runs_last24h_limit100" / "20260315T203138Z"
    _write_json(
        traced_run / "run.json",
        {
            "run_id": "20260315T203138Z",
            "status": "completed",
            "started_at": "2026-03-15T20:31:38+00:00",
            "finished_at": "2026-03-15T20:42:32+00:00",
            "model": "gpt-5.4",
            "thread_count": 100,
            "kept_count": 12,
            "issue_count": 6,
            "digest_path": str(traced_run / "digest.md"),
            "phases_path": str(traced_run / "phases.json"),
            "llm_calls_dir": str(traced_run / "llm_calls"),
        },
    )
    _write_json(
        traced_run / "phases.json",
        [
            {
                "name": "render_digest",
                "status": "completed",
                "artifact_paths": [str(traced_run / "digest.md")],
                "counts": {"issues": 6},
            }
        ],
    )
    (traced_run / "digest.md").write_text(
        (
            "# xs2n Digest Issue 20260315T203138Z\n\n"
            "## Top Issues\n\n"
            "### Debate over whether interest or discipline matters more in mastering a skill\n"
        ),
        encoding="utf-8",
    )
    (traced_run / "llm_calls").mkdir(parents=True)

    runs = scan_runs(data_dir)

    assert [run.run_id for run in runs] == [
        "20260315T203138Z",
        "20260307T173044Z",
        "20260307T171055Z",
    ]
    assert runs[0].root_name == "report_runs_last24h_limit100"
    assert runs[0].status == "completed"
    assert runs[1].status == "unknown"
    assert runs[0].digest_title == (
        "Debate over whether interest or discipline matters more in mastering a skill"
    )
    assert runs[1].digest_title == "Run 20260307T173044Z"
    assert runs[2].digest_title == "No high-signal issues were produced in this run"


def test_list_run_artifacts_uses_filesystem_and_keeps_directories_collapsed(
    tmp_path: Path,
) -> None:
    data_dir = tmp_path / "data"
    run_dir = data_dir / "report_runs_subset" / "20260313T003317Z"
    llm_calls_dir = run_dir / "llm_calls"
    llm_calls_dir.mkdir(parents=True)

    _write_json(
        run_dir / "run.json",
        {
            "run_id": "20260313T003317Z",
            "status": "completed",
            "started_at": "2026-03-13T00:33:17+00:00",
            "model": "gpt-5.4",
            "thread_count": 12,
            "kept_count": 0,
            "issue_count": 0,
            "digest_path": str(run_dir / "digest.md"),
            "phases_path": str(run_dir / "phases.json"),
            "llm_calls_dir": str(llm_calls_dir),
        },
    )
    _write_json(
        run_dir / "phases.json",
        [
            {
                "name": "render_digest",
                "status": "completed",
                "artifact_paths": [
                    str(run_dir / "digest.md"),
                    str(run_dir / "missing.json"),
                ],
            }
        ],
    )
    (run_dir / "digest.md").write_text(
        (
            "# xs2n Digest Issue 20260313T003317Z\n\n"
            "## Top Issues\n\n"
            "### Quiet test issue\n"
        ),
        encoding="utf-8",
    )
    (run_dir / "run.json").touch()
    (llm_calls_dir / "001_trace.json").write_text("{\"ok\": true}\n", encoding="utf-8")

    run = scan_runs(data_dir)[0]
    phases = load_phase_records(run)
    artifacts = list_run_artifacts(run)

    assert len(phases) == 1
    assert phases[0].artifact_paths == [
        str(run_dir / "digest.md"),
        str(run_dir / "missing.json"),
    ]
    assert [artifact.name for artifact in artifacts[:4]] == [
        "digest.md",
        "run.json",
        "phases.json",
        "llm_calls/",
    ]
    digest_artifact = next(
        artifact for artifact in artifacts if artifact.name == "digest.md"
    )
    assert run.digest_title == "Quiet test issue"
    assert digest_artifact.phase_name == "render_digest"
    assert all(artifact.name != "missing.json" for artifact in artifacts)
    assert all(
        artifact.name != "llm_calls/001_trace.json"
        for artifact in artifacts
    )


def test_list_artifact_sections_builds_curated_shortcuts(
    tmp_path: Path,
) -> None:
    data_dir = tmp_path / "data"
    run_dir = data_dir / "report_runs" / "20260315T203138Z"
    (run_dir / "llm_calls").mkdir(parents=True)
    (run_dir / "digest.md").write_text("# digest\n", encoding="utf-8")
    (run_dir / "run.json").write_text("{}\n", encoding="utf-8")
    (run_dir / "phases.json").write_text("[]\n", encoding="utf-8")
    (run_dir / "notes.txt").write_text("hello\n", encoding="utf-8")

    run = scan_runs(data_dir)[0]
    artifacts = list_run_artifacts(run)
    sections = list_artifact_sections(artifacts)

    assert [section.browser_label for section in sections] == [
        "◆ Digest",
        "▣ Run metadata",
        "↻ Phase trace",
        "▸ LLM calls",
    ]
    assert [section.artifact_name for section in sections] == [
        "digest.md",
        "run.json",
        "phases.json",
        "llm_calls/",
    ]


def test_scan_runs_prefers_primary_html_artifact_from_metadata(
    tmp_path: Path,
) -> None:
    data_dir = tmp_path / "data"
    run_dir = data_dir / "report_runs" / "20260318T120000Z"
    run_dir.mkdir(parents=True)
    (run_dir / "digest.html").write_text(
        "<!doctype html><html><body><h1>Chip Race</h1></body></html>\n",
        encoding="utf-8",
    )
    _write_json(
        run_dir / "run.json",
        {
            "run_id": "20260318T120000Z",
            "status": "completed",
            "primary_artifact_path": str(run_dir / "digest.html"),
            "digest_title": "Chip Race",
        },
    )

    run = scan_runs(data_dir)[0]
    artifacts = list_run_artifacts(run)
    sections = list_artifact_sections(artifacts)

    assert run.digest_path == run_dir / "digest.html"
    assert run.digest_title == "Chip Race"
    assert sections[0].artifact_name == "digest.html"


def test_load_artifact_text_pretty_prints_json_and_lists_directories(
    tmp_path: Path,
) -> None:
    json_path = tmp_path / "artifact.json"
    _write_json(json_path, {"alpha": 1, "beta": ["x", "y"]})

    directory = tmp_path / "llm_calls"
    directory.mkdir()
    (directory / "001_trace.json").write_text("{\"ok\": true}\n", encoding="utf-8")

    json_text = load_artifact_text(json_path)
    directory_text = load_artifact_text(directory)
    missing_text = load_artifact_text(tmp_path / "missing.txt")

    assert '"alpha": 1' in json_text
    assert "llm_calls/" in directory_text
    assert "001_trace.json" in directory_text
    assert "Missing artifact:" in missing_text


def test_load_artifact_preview_truncates_large_json_without_pretty_printing(
    tmp_path: Path,
) -> None:
    json_path = tmp_path / "large.json"
    json_path.write_text(
        "{\"payload\":\"" + ("x" * 90000) + "\"}\n",
        encoding="utf-8",
    )
    artifact = ArtifactRecord(
        name="large.json",
        path=json_path,
        kind="json",
        exists=True,
    )

    preview = load_artifact_preview(artifact)

    assert preview.truncated is True
    assert preview.render_kind == "text"
    assert preview.summary is not None
    assert "truncated preview" in preview.summary.lower()
    assert "payload" in preview.body
    assert len(preview.body) < 70000


def test_delete_runs_removes_selected_run_directories(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    first_run = data_dir / "report_runs" / "20260315T203138Z"
    second_run = data_dir / "report_runs" / "20260315T203500Z"
    first_run.mkdir(parents=True)
    second_run.mkdir(parents=True)

    runs = scan_runs(data_dir)

    delete_runs([run for run in runs if run.run_id == "20260315T203138Z"])

    assert first_run.exists() is False
    assert second_run.exists() is True
    assert [run.run_id for run in scan_runs(data_dir)] == ["20260315T203500Z"]


def test_delete_runs_ignores_missing_directories(tmp_path: Path) -> None:
    missing_run = tmp_path / "data" / "report_runs" / "20260315T203138Z"

    delete_runs(
        [
            SimpleNamespace(run_dir=missing_run),
        ]
    )

    assert missing_run.exists() is False
