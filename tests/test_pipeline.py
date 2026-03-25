from __future__ import annotations

from pathlib import Path

import pytest

from xs2n.agents.pipeline import run_digest_pipeline
from xs2n.agents.schemas import (
    DigestOutput,
    IssueSelectionResult,
    IssueWriteResult,
    Post,
    Thread,
    ThreadFilterResult,
)


def build_thread(*, thread_id: str, account_handle: str, text: str, created_at: str) -> Thread:
    return Thread(
        thread_id=thread_id,
        account_handle=account_handle,
        posts=[
            Post(
                post_id=f"{thread_id}-post",
                author_handle=account_handle,
                created_at=created_at,
                text=text,
                url=f"https://x.com/{account_handle}/status/{thread_id}",
            )
        ],
    )


def test_run_digest_pipeline_writes_only_final_digest_json(tmp_path: Path) -> None:
    output_path = tmp_path / "digest.json"
    threads = [
        build_thread(
            thread_id="thread-1",
            account_handle="alice",
            text="AI inference costs are dropping fast.",
            created_at="2026-03-21T10:00:00Z",
        ),
        build_thread(
            thread_id="thread-2",
            account_handle="bob",
            text="gm",
            created_at="2026-03-21T11:00:00Z",
        ),
    ]

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
        threads=threads,
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
    assert sorted(path.name for path in tmp_path.iterdir()) == ["digest.json"]


def test_run_digest_pipeline_keeps_selection_issue_slug_when_write_step_disagrees(
    tmp_path: Path,
) -> None:
    output_path = tmp_path / "digest.json"
    threads = [
        build_thread(
            thread_id="thread-1",
            account_handle="alice",
            text="Inference costs keep falling.",
            created_at="2026-03-21T10:00:00Z",
        ),
        build_thread(
            thread_id="thread-2",
            account_handle="bob",
            text="Serving costs are compressing again.",
            created_at="2026-03-21T11:00:00Z",
        ),
    ]

    class FakeLLM:
        def run(self, *, prompt, payload, schema):  # noqa: ANN001, ANN204
            thread_id = payload.get("thread", {}).get("thread_id")
            if schema is ThreadFilterResult:
                return ThreadFilterResult(
                    keep=True,
                    filter_reason="Real signal.",
                )
            if schema is IssueSelectionResult:
                if thread_id == "thread-1":
                    return IssueSelectionResult(
                        action="create_new_issue",
                        issue_slug="ai_costs",
                        reasoning="Start the issue.",
                    )
                return IssueSelectionResult(
                    action="update_existing_issue",
                    issue_slug="ai_costs",
                    reasoning="Same running story.",
                )
            if schema is IssueWriteResult:
                if thread_id == "thread-1":
                    return IssueWriteResult(
                        issue_slug="ai_costs",
                        issue_title="AI Costs Keep Sliding",
                        issue_summary="The issue tracks falling AI serving costs.",
                        thread_title="Costs fall again",
                        thread_summary="The thread says costs keep moving down.",
                        why_this_thread_belongs="It starts the story.",
                    )
                return IssueWriteResult(
                    issue_slug="rogue_issue_slug",
                    issue_title="AI Costs Keep Sliding",
                    issue_summary="The issue tracks falling AI serving costs.",
                    thread_title="Costs compress again",
                    thread_summary="The thread adds more evidence.",
                    why_this_thread_belongs="It updates the same story.",
                )
            raise AssertionError(f"Unexpected schema: {schema}")

    digest = run_digest_pipeline(
        threads=threads,
        output_file=output_path,
        model="gpt-5.4-mini",
        llm=FakeLLM(),
    )

    assert digest.issue_count == 1
    assert len(digest.issues) == 1
    assert digest.issues[0].slug == "ai_costs"
    assert [thread.thread_id for thread in digest.issues[0].threads] == [
        "thread-1",
        "thread-2",
    ]


def test_run_digest_pipeline_fails_early_for_thread_without_posts(tmp_path: Path) -> None:
    output_path = tmp_path / "digest.json"

    with pytest.raises(ValueError, match="has no posts"):
        run_digest_pipeline(
            threads=[
                Thread(
                    thread_id="thread-1",
                    account_handle="alice",
                    posts=[],
                )
            ],
            output_file=output_path,
            model="gpt-5.4-mini",
            llm=object(),
        )
