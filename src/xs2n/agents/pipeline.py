import json
from collections import OrderedDict
from datetime import datetime, timezone

from xs2n.agents.llm import LLM
from xs2n.agents.schemas import (
    DigestIssue,
    DigestOutput,
    DigestThread,
    FilteredThread,
    IssueSelectionResult,
    IssueWriteResult,
    PipelineInput,
    ThreadFilterResult,
)


DEFAULT_MODEL = "gpt-5.4-mini"
FILTER_THREADS_PROMPT = (
    "You review one X/Twitter thread for a low-noise issue digest. "
    "Drop only items that are obviously shallow, spammy, repetitive, or clearly "
    "not worth a serious reader's attention. Default to keeping borderline but real signal."
)
SELECT_ISSUE_PROMPT = (
    "You receive one kept X/Twitter thread and the current issue list for a "
    "magazine-style digest. Decide whether this thread should create a new issue "
    "or update an existing one. Reuse an issue only when it is clearly the same running story."
)
WRITE_ISSUE_PROMPT = (
    "You write the issue copy for one kept X/Twitter thread in a simple magazine digest. "
    "Return the final issue slug, issue title, issue summary, a short thread title, "
    "a short thread summary, and why this thread belongs in the issue."
)


def _slugify_issue(value, *, fallback):
    cleaned = "".join(
        character.lower() if character.isalnum() else "_"
        for character in value.strip()
    ).strip("_")
    collapsed = "_".join(part for part in cleaned.split("_") if part)
    return collapsed or fallback


def _validate_threads_have_posts(threads):
    for thread in threads:
        if not thread.posts:
            raise ValueError(f"Thread `{thread.thread_id}` has no posts.")


def run_digest_pipeline(
    *,
    input_file,
    output_file,
    model=DEFAULT_MODEL,
    api_key=None,
    llm=None,
):
    payload = json.loads(input_file.read_text(encoding="utf-8"))
    threads = PipelineInput.model_validate(payload).threads
    _validate_threads_have_posts(threads)
    digest_llm = llm or LLM(model=model, api_key=api_key)

    filtered_threads = []
    for thread in threads:
        result = digest_llm.run(
            prompt=FILTER_THREADS_PROMPT,
            payload={"thread": thread.model_dump(mode="json")},
            schema=ThreadFilterResult,
        )
        filtered_threads.append(
            FilteredThread(
                thread_id=thread.thread_id,
                account_handle=thread.account_handle,
                posts=thread.posts,
                keep=result.keep,
                filter_reason=result.filter_reason,
            )
        )

    kept_threads = [thread for thread in filtered_threads if thread.keep]
    grouped_threads = OrderedDict()
    issue_titles = {}
    issue_summaries = {}
    current_issues = []
    for thread in kept_threads:
        compact_issues = [
            {"slug": issue.slug, "title": issue.title, "summary": issue.summary}
            for issue in current_issues
        ]
        selection = digest_llm.run(
            prompt=SELECT_ISSUE_PROMPT,
            payload={"thread": thread.model_dump(mode="json"), "issues": compact_issues},
            schema=IssueSelectionResult,
        )
        resolved_slug = _slugify_issue(
            selection.issue_slug or thread.thread_id,
            fallback=thread.thread_id,
        )
        current_slugs = {issue.slug for issue in current_issues}
        if selection.action == "update_existing_issue" and resolved_slug not in current_slugs:
            selection = IssueSelectionResult(
                action="create_new_issue",
                issue_slug=_slugify_issue(thread.thread_id, fallback=thread.thread_id),
                reasoning=selection.reasoning,
            )
        else:
            selection = IssueSelectionResult(
                action=selection.action,
                issue_slug=resolved_slug,
                reasoning=selection.reasoning,
            )
        issue_write = digest_llm.run(
            prompt=WRITE_ISSUE_PROMPT,
            payload={
                "thread": thread.model_dump(mode="json"),
                "issues": compact_issues,
                "selection": selection.model_dump(mode="json"),
            },
            schema=IssueWriteResult,
        )
        issue_slug = selection.issue_slug or thread.thread_id
        digest_thread = DigestThread(
            thread_id=thread.thread_id,
            account_handle=thread.account_handle,
            thread_title=issue_write.thread_title.strip() or thread.primary_post.text[:80],
            thread_summary=issue_write.thread_summary.strip() or thread.primary_post.text,
            why_this_thread_belongs=(
                issue_write.why_this_thread_belongs.strip() or "Part of the same issue."
            ),
            filter_reason=thread.filter_reason,
            source_urls=thread.source_urls,
        )
        grouped_threads.setdefault(issue_slug, []).append(digest_thread)
        issue_titles[issue_slug] = (
            issue_write.issue_title.strip() or issue_slug.replace("_", " ").title()
        )
        issue_summaries[issue_slug] = (
            issue_write.issue_summary.strip() or thread.primary_post.text
        )
        current_issues = [
            DigestIssue(
                slug=slug,
                title=issue_titles[slug],
                summary=issue_summaries[slug],
                threads=grouped_threads[slug],
            )
            for slug in grouped_threads
        ]

    generated_at = (
        max(post.created_at for thread in threads for post in thread.posts)
        if threads
        else datetime.now(timezone.utc)
    )
    digest = DigestOutput(
        generated_at=generated_at,
        issue_count=len(current_issues),
        issues=current_issues,
    )
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(f"{digest.model_dump_json(indent=2)}\n", encoding="utf-8")
    return digest
