from __future__ import annotations

import json
import os
from typing import Any, cast

from langchain_openai import ChatOpenAI
from pydantic import BaseModel

from .pipeline import (
    DEFAULT_MAX_ISSUES,
    DEFAULT_REPORT_MODEL,
    AssembledUnit,
    AssemblyResult,
    CategorizationResult,
    CategorizedUnit,
    ConversationCandidate,
    FilteredUnit,
    IssueCluster,
    IssueClusterResult,
    SignalResult,
    SignalUnit,
    TaxonomyConfig,
    aggregate_engagement,
    virality_score,
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
            f"{instructions}\n\nInput JSON:\n{json.dumps(_to_jsonable(payload), ensure_ascii=False, indent=2)}"
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


def _to_jsonable(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, list):
        return [_to_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {key: _to_jsonable(item) for key, item in value.items()}
    return value


def assemble_units(
    *,
    backend: OpenAIDigestBackend | Any,
    taxonomy: TaxonomyConfig,
    candidates: list[ConversationCandidate],
) -> list[AssembledUnit]:
    assembled_units: list[AssembledUnit] = []
    for candidate in candidates:
        assembly = backend.assemble_conversation(taxonomy=taxonomy, candidate=candidate)
        included_ids = [
            tweet_id
            for tweet_id in assembly.include_tweet_ids
            if any(tweet.tweet_id == tweet_id for tweet in candidate.tweets)
        ]
        if not included_ids:
            included_ids = [candidate.tweets[0].tweet_id]
        highlight_ids = [
            tweet_id
            for tweet_id in assembly.highlight_tweet_ids
            if tweet_id in included_ids
        ]
        if not highlight_ids:
            highlight_ids = included_ids[:1]
        tweets = [tweet for tweet in candidate.tweets if tweet.tweet_id in included_ids]
        assembled_units.append(
            AssembledUnit(
                unit_id=candidate.unit_id,
                conversation_id=candidate.conversation_id,
                account_handle=candidate.account_handle,
                title=assembly.title,
                summary=assembly.summary,
                why_this_is_one_unit=assembly.why_this_is_one_unit,
                tweets=tweets,
                included_tweet_ids=included_ids,
                highlight_tweet_ids=highlight_ids,
                standout_reply_ids=[
                    tweet_id
                    for tweet_id in candidate.standout_reply_ids
                    if tweet_id in included_ids
                ],
            )
        )
    return assembled_units


def categorize_units(
    *,
    backend: OpenAIDigestBackend | Any,
    taxonomy: TaxonomyConfig,
    units: list[AssembledUnit],
) -> list[CategorizedUnit]:
    allowed_categories = {category.slug for category in taxonomy.categories}
    categorized: list[CategorizedUnit] = []
    for unit in units:
        result = backend.categorize_conversation(taxonomy=taxonomy, unit=unit)
        category = result.category if result.category in allowed_categories else "analysis"
        categorized.append(
            CategorizedUnit(
                **unit.model_dump(),
                category=category,
                subcategory=result.subcategory,
                editorial_angle=result.editorial_angle,
                reasoning=result.reasoning,
            )
        )
    return categorized


def extract_signals(
    *,
    backend: OpenAIDigestBackend | Any,
    taxonomy: TaxonomyConfig,
    units: list[FilteredUnit],
    previous_threads,
) -> list[SignalUnit]:
    signal_units: list[SignalUnit] = []
    for unit in units:
        if not unit.keep:
            continue
        signal = backend.extract_signal(taxonomy=taxonomy, unit=unit)
        previous_state = previous_threads.get(unit.conversation_id)
        engagement_totals = aggregate_engagement(unit.tweets)
        current_virality = sum(virality_score(tweet) for tweet in unit.tweets)
        previous_virality = previous_state.virality_score if previous_state is not None else 0.0
        delta = current_virality - previous_virality

        if delta > 0.5:
            momentum = "rising"
        elif delta < -0.2:
            momentum = "cooling"
        else:
            momentum = "steady"

        numeric_heat = (
            current_virality >= 5.0
            or delta > 0.75
            or engagement_totals["reply_count"] >= 10
        )
        if numeric_heat and signal.disagreement_present:
            heat_status = "heated"
        elif numeric_heat or signal.disagreement_present:
            heat_status = "still_active"
        elif (
            previous_state is not None
            and previous_state.heat_status in {"heated", "still_active"}
        ):
            heat_status = "cooling_off"
        else:
            heat_status = "watch"

        highlighted_ids = set(unit.highlight_tweet_ids or unit.included_tweet_ids[:1])
        source_urls = [
            tweet.source_url
            for tweet in unit.tweets
            if tweet.tweet_id in highlighted_ids
        ]
        if not source_urls:
            source_urls = [tweet.source_url for tweet in unit.tweets[:1]]
        signal_units.append(
            SignalUnit(
                unit_id=unit.unit_id,
                conversation_id=unit.conversation_id,
                account_handle=unit.account_handle,
                title=unit.title,
                summary=unit.summary,
                category=unit.category,
                subcategory=unit.subcategory,
                editorial_angle=unit.editorial_angle,
                tweets=unit.tweets,
                included_tweet_ids=unit.included_tweet_ids,
                highlight_tweet_ids=unit.highlight_tweet_ids,
                standout_reply_ids=unit.standout_reply_ids,
                headline=signal.headline,
                main_claim=signal.main_claim,
                why_it_matters=signal.why_it_matters,
                key_entities=signal.key_entities,
                disagreement_present=signal.disagreement_present,
                disagreement_summary=signal.disagreement_summary,
                novelty_label=signal.novelty_label,
                signal_score=signal.signal_score,
                virality_score=current_virality,
                engagement_totals=engagement_totals,
                heat_status=heat_status,
                momentum=momentum,
                source_urls=source_urls,
            )
        )
    signal_units.sort(
        key=lambda unit: (unit.signal_score, unit.virality_score),
        reverse=True,
    )
    return signal_units


def cluster_issues(
    *,
    backend: OpenAIDigestBackend | Any,
    taxonomy: TaxonomyConfig,
    units: list[SignalUnit],
) -> list[IssueCluster]:
    if not units:
        return []
    cluster_result = backend.cluster_issues(taxonomy=taxonomy, units=units)
    known_unit_ids = {unit.unit_id for unit in units}
    clusters: list[IssueCluster] = []
    assigned: set[str] = set()
    for issue in cluster_result.issues:
        valid_ids = [
            unit_id
            for unit_id in issue.unit_ids
            if unit_id in known_unit_ids and unit_id not in assigned
        ]
        if not valid_ids:
            continue
        assigned.update(valid_ids)
        clusters.append(
            IssueCluster(
                title=issue.title,
                summary=issue.summary,
                unit_ids=valid_ids,
            )
        )

    unassigned = [unit for unit in units if unit.unit_id not in assigned]
    for unit in unassigned:
        clusters.append(
            IssueCluster(
                title=unit.headline,
                summary=unit.why_it_matters,
                unit_ids=[unit.unit_id],
            )
        )
    return clusters[:DEFAULT_MAX_ISSUES]
