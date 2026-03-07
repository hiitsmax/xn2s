from __future__ import annotations

from ..backend import DigestBackend
from ..models import AssembledUnit, ConversationCandidate, TaxonomyConfig


def assemble_units(
    *,
    backend: DigestBackend,
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
        tweets = [
            tweet
            for tweet in candidate.tweets
            if tweet.tweet_id in included_ids
        ]
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
