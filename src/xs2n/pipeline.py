from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from xs2n.llm import DigestLLM
from xs2n.schemas import DigestOutput, PipelineInput, ThreadInput
from xs2n.steps.filter_threads import run as filter_threads
from xs2n.steps.group_issues import run as group_issues


DEFAULT_MODEL = "gpt-5.4-mini"


def load_threads(*, input_file: Path) -> list[ThreadInput]:
    payload = json.loads(input_file.read_text(encoding="utf-8"))
    pipeline_input = PipelineInput.model_validate(payload)
    return pipeline_input.threads


def run_digest_pipeline(
    *,
    input_file: Path,
    output_file: Path,
    model: str = DEFAULT_MODEL,
    api_key: str | None = None,
    llm: Any | None = None,
) -> DigestOutput:
    threads = load_threads(input_file=input_file)
    digest_llm = llm or DigestLLM(model=model, api_key=api_key)
    filtered_threads = filter_threads(
        llm=digest_llm,
        threads=threads,
    )
    issues = group_issues(
        llm=digest_llm,
        threads=filtered_threads,
    )
    generated_at = (
        max(
            post.created_at
            for thread in threads
            for post in thread.posts
        )
        if threads
        else datetime.now(timezone.utc)
    )
    digest = DigestOutput(
        generated_at=generated_at,
        issue_count=len(issues),
        issues=issues,
    )
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(f"{digest.model_dump_json(indent=2)}\n", encoding="utf-8")
    return digest
