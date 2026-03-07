from __future__ import annotations

from typing import Literal

from ..backend import DigestBackend
from ..config import DEFAULT_KEEP_HEAT_STATUSES
from ..models import FilteredUnit, SignalUnit, TaxonomyConfig, ThreadState
from .selection import aggregate_engagement, virality_score


def _signal_heat_state(
    *,
    unit: FilteredUnit,
    signal,
    previous_state: ThreadState | None,
) -> tuple[
    Literal["heated", "still_active", "cooling_off", "watch"],
    Literal["rising", "steady", "cooling"],
    float,
    dict[str, int],
]:
    engagement_totals = aggregate_engagement(unit.tweets)
    current_virality = sum(virality_score(tweet) for tweet in unit.tweets)
    previous_virality = previous_state.virality_score if previous_state is not None else 0.0
    delta = current_virality - previous_virality

    if delta > 0.5:
        momentum: Literal["rising", "steady", "cooling"] = "rising"
    elif delta < -0.2:
        momentum = "cooling"
    else:
        momentum = "steady"

    numeric_heat = current_virality >= 5.0 or delta > 0.75 or engagement_totals["reply_count"] >= 10
    if numeric_heat and signal.disagreement_present:
        heat_status: Literal["heated", "still_active", "cooling_off", "watch"] = "heated"
    elif numeric_heat or signal.disagreement_present:
        heat_status = "still_active"
    elif previous_state is not None and previous_state.heat_status in DEFAULT_KEEP_HEAT_STATUSES:
        heat_status = "cooling_off"
    else:
        heat_status = "watch"
    return heat_status, momentum, current_virality, engagement_totals


def extract_signals(
    *,
    backend: DigestBackend,
    taxonomy: TaxonomyConfig,
    units: list[FilteredUnit],
    previous_threads: dict[str, ThreadState],
) -> list[SignalUnit]:
    signal_units: list[SignalUnit] = []
    for unit in units:
        if not unit.keep:
            continue
        signal = backend.extract_signal(taxonomy=taxonomy, unit=unit)
        previous_state = previous_threads.get(unit.conversation_id)
        heat_status, momentum, run_virality_score, engagement_totals = _signal_heat_state(
            unit=unit,
            signal=signal,
            previous_state=previous_state,
        )
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
                virality_score=run_virality_score,
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
