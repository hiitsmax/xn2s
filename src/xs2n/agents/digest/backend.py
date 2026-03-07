from __future__ import annotations

import json
import os
from typing import Any, cast

from langchain_openai import ChatOpenAI
from pydantic import BaseModel

from .config import DEFAULT_MAX_ISSUES, DEFAULT_REPORT_MODEL
from .io import to_jsonable
from .models import (
    AssembledUnit,
    AssemblyResult,
    CategorizationResult,
    ConversationCandidate,
    DigestBackend,
    FilteredUnit,
    IssueClusterResult,
    SignalResult,
    SignalUnit,
    TaxonomyConfig,
)


class OpenAIDigestBackend:
    def __init__(
        self,
        *,
        model: str = DEFAULT_REPORT_MODEL,
        api_key: str | None = None,
    ) -> None:
        resolved_key = api_key or os.getenv("OPENAI_API_KEY")
        if not resolved_key:
            raise RuntimeError(
                "OPENAI_API_KEY is required for `xs2n report digest`. "
                "Export the key and retry."
            )
        self._model = ChatOpenAI(model=model, temperature=0, api_key=resolved_key)

    def _invoke_structured(
        self,
        *,
        instructions: str,
        payload: Any,
        schema: type[BaseModel],
    ) -> BaseModel:
        structured_model = self._model.with_structured_output(schema, method="json_schema")
        response = structured_model.invoke(
            f"{instructions}\n\nInput JSON:\n{json.dumps(to_jsonable(payload), ensure_ascii=False, indent=2)}"
        )
        return cast(BaseModel, response)

    def assemble_conversation(
        self,
        *,
        taxonomy: TaxonomyConfig,
        candidate: ConversationCandidate,
    ) -> AssemblyResult:
        allowed_ids = [tweet.tweet_id for tweet in candidate.tweets]
        response = self._invoke_structured(
            instructions=(
                "You assemble one high-signal narrative unit from a candidate X/Twitter "
                "conversation bundle for a magazine-style digest. Keep all source-authored "
                "tweets that materially belong to the same thread or argument. Keep outside "
                "replies only when they clearly shape the interpretation, disagreement, or "
                "social proof. Return only tweet IDs present in the bundle. "
                f"Allowed tweet IDs: {allowed_ids}. "
                "highlight_tweet_ids must be a subset of include_tweet_ids."
            ),
            payload=candidate,
            schema=AssemblyResult,
        )
        return cast(AssemblyResult, response)

    def categorize_conversation(
        self,
        *,
        taxonomy: TaxonomyConfig,
        unit: AssembledUnit,
    ) -> CategorizationResult:
        categories = {category.slug: category.description for category in taxonomy.categories}
        response = self._invoke_structured(
            instructions=(
                "You are categorizing one conversation unit for a high-signal X/Twitter digest. "
                "Pick exactly one top-level category slug from the provided taxonomy. "
                "Use the most informative bucket, not the safest one."
            ),
            payload={"taxonomy": categories, "unit": unit},
            schema=CategorizationResult,
        )
        return cast(CategorizationResult, response)

    def extract_signal(
        self,
        *,
        taxonomy: TaxonomyConfig,
        unit: FilteredUnit,
    ) -> SignalResult:
        response = self._invoke_structured(
            instructions=(
                "You extract the core signal from one kept conversation unit for a magazine-style "
                "digest. Be concise, concrete, and avoid generic filler. disagreement_present "
                "should be true only when there is real tension, pushback, or competing frames."
            ),
            payload=unit,
            schema=SignalResult,
        )
        return cast(SignalResult, response)

    def cluster_issues(
        self,
        *,
        taxonomy: TaxonomyConfig,
        units: list[SignalUnit],
    ) -> IssueClusterResult:
        response = self._invoke_structured(
            instructions=(
                "You group high-signal conversation units into a small set of magazine issue "
                "sections. Merge units that are clearly about the same live argument, storyline, "
                "or controversy. Every unit_id should appear at most once."
            ),
            payload={"units": units, "max_issues": DEFAULT_MAX_ISSUES},
            schema=IssueClusterResult,
        )
        return cast(IssueClusterResult, response)


__all__ = ["DigestBackend", "OpenAIDigestBackend"]
