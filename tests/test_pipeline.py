from __future__ import annotations

import json
from pathlib import Path

from xs2n.pipeline import run_digest_pipeline
from xs2n.schemas import (
    DigestOutput,
    IssueSelectionResult,
    IssueWriteResult,
    ThreadFilterResult,
)


def test_run_digest_pipeline_writes_only_final_digest_json(tmp_path: Path) -> None:
    input_path = tmp_path / "threads.json"
    output_path = tmp_path / "digest.json"
    input_path.write_text(
        json.dumps(
            {
                "threads": [
                    {
                        "thread_id": "thread-1",
                        "account_handle": "alice",
                        "posts": [
                            {
                                "post_id": "post-1",
                                "author_handle": "alice",
                                "created_at": "2026-03-21T10:00:00Z",
                                "text": "AI inference costs are dropping fast.",
                                "url": "https://x.com/alice/status/post-1",
                            }
                        ],
                    },
                    {
                        "thread_id": "thread-2",
                        "account_handle": "bob",
                        "posts": [
                            {
                                "post_id": "post-2",
                                "author_handle": "bob",
                                "created_at": "2026-03-21T11:00:00Z",
                                "text": "gm",
                                "url": "https://x.com/bob/status/post-2",
                            }
                        ],
                    },
                ]
            }
        ),
        encoding="utf-8",
    )

    class FakeLLM:
        def run(self, *, prompt, payload, schema):  # noqa: ANN001, ANN204
            thread_id = payload.get("thread", {}).get("thread_id")
            if schema is ThreadFilterResult:
                if thread_id == "thread-1":
                    return ThreadFilterResult(
                        keep=True,
                        filter_reason="Concrete industry signal.",
                    )
                return ThreadFilterResult(
                    keep=False,
                    filter_reason="Too shallow.",
                )
            if schema is IssueSelectionResult:
                return IssueSelectionResult(
                    action="create_new_issue",
                    issue_slug="ai_costs",
                    reasoning="Same emerging theme.",
                )
            if schema is IssueWriteResult:
                return IssueWriteResult(
                    issue_slug="ai_costs",
                    issue_title="AI Costs Keep Sliding",
                    issue_summary="Multiple threads point to continued cost compression.",
                    thread_title="Inference costs falling",
                    thread_summary="The thread argues that serving costs are dropping quickly.",
                    why_this_thread_belongs="It is direct evidence for the cost trend.",
                )
            raise AssertionError(f"Unexpected schema: {schema}")

    digest = run_digest_pipeline(
        input_file=input_path,
        output_file=output_path,
        model="gpt-5.4-mini",
        llm=FakeLLM(),
    )

    saved_output = DigestOutput.model_validate_json(output_path.read_text(encoding="utf-8"))

    assert digest == saved_output
    assert digest.issue_count == 1
    assert len(digest.issues) == 1
    assert digest.issues[0].slug == "ai_costs"
    assert len(digest.issues[0].threads) == 1
    assert digest.issues[0].threads[0].thread_id == "thread-1"
    assert sorted(path.name for path in tmp_path.iterdir()) == ["digest.json", "threads.json"]
