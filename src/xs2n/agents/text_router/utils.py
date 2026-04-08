from __future__ import annotations

import string

from xs2n.schemas.clustering import TweetQueueItem
from xs2n.schemas.routing import PackedRoutingBatch, RoutingResult, RoutingTweetRow


_TRANSPORT_BLOCKLIST = {",", "|"}
_COMPACT_ID_PREFIX = string.digits + string.ascii_uppercase + string.ascii_lowercase
# Keep compact ids short while excluding the separators used by the transport.
COMPACT_ID_ALPHABET = _COMPACT_ID_PREFIX + "".join(
    character
    for character in string.punctuation
    if character not in _TRANSPORT_BLOCKLIST and character not in _COMPACT_ID_PREFIX
)
_COMPACT_ID_LOOKUP = {character: index for index, character in enumerate(COMPACT_ID_ALPHABET)}
_FIELD_SEPARATOR = "\t"
_ROW_SEPARATOR = "\n"
_GROUP_SEPARATOR = "|"
_ID_SEPARATOR = ","


def encode_compact_id(value: int) -> str:
    if value < 0:
        raise ValueError("Compact ids require a non-negative integer.")

    base = len(COMPACT_ID_ALPHABET)
    if value == 0:
        return COMPACT_ID_ALPHABET[0]

    digits: list[str] = []
    current = value
    while current > 0:
        current, remainder = divmod(current, base)
        digits.append(COMPACT_ID_ALPHABET[remainder])
    return "".join(reversed(digits))


def decode_compact_id(value: str) -> int:
    cleaned_value = value.strip()
    if not cleaned_value:
        raise ValueError("Compact ids cannot be empty.")

    base = len(COMPACT_ID_ALPHABET)
    decoded = 0
    for character in cleaned_value:
        if character not in _COMPACT_ID_LOOKUP:
            raise ValueError(f"Unsupported compact id character: {character!r}")
        decoded = (decoded * base) + _COMPACT_ID_LOOKUP[character]
    return decoded


def build_packed_routing_batch(rows: list[RoutingTweetRow]) -> PackedRoutingBatch:
    short_to_tweet_id: dict[str, str] = {}
    packed_rows: list[str] = []

    for index, row in enumerate(rows):
        # The model sees only compact transport ids; we keep the real tweet ids locally.
        short_id = encode_compact_id(index)
        short_to_tweet_id[short_id] = row.tweet_id
        packed_rows.append(
            _FIELD_SEPARATOR.join(
                [
                    short_id,
                    _normalize_field(row.text),
                    _normalize_field(row.quote_text),
                    _normalize_field(row.image_description),
                    _normalize_field(row.url_hint),
                ]
            )
        )

    return PackedRoutingBatch(
        prompt=_ROW_SEPARATOR.join(packed_rows),
        short_to_tweet_id=short_to_tweet_id,
    )


def parse_routing_output(
    output: str,
    *,
    packed_batch: PackedRoutingBatch,
) -> RoutingResult:
    normalized_output = output.strip()
    if not normalized_output:
        raise ValueError("Routing output cannot be empty.")
    if any(character in normalized_output for character in "\r\n"):
        raise ValueError("Routing output must be exactly one line.")

    groups = normalized_output.split(_GROUP_SEPARATOR)
    if len(groups) != 4:
        raise ValueError("Routing output must contain exactly four pipe-separated groups.")

    expected_short_ids = set(packed_batch.short_to_tweet_id)
    seen_short_ids: set[str] = set()
    expanded_groups: list[list[str]] = []

    for group in groups:
        # Validate and expand in one pass so completeness and uniqueness checks
        # stay next to the short-id to tweet-id mapping.
        short_ids = _parse_group(group)
        expanded_ids: list[str] = []
        for short_id in short_ids:
            if short_id not in expected_short_ids:
                raise ValueError(f"Unknown compact id in routing output: {short_id!r}")
            if short_id in seen_short_ids:
                raise ValueError("Each compact id must appear exactly once in routing output.")
            seen_short_ids.add(short_id)
            expanded_ids.append(packed_batch.short_to_tweet_id[short_id])
        expanded_groups.append(expanded_ids)

    if seen_short_ids != expected_short_ids:
        raise ValueError("Each compact id must appear exactly once in routing output.")

    return RoutingResult(
        plain_ids=expanded_groups[0],
        ambiguous_ids=expanded_groups[1],
        image_ids=expanded_groups[2],
        external_ids=expanded_groups[3],
    )


def build_routing_rows_from_queue_items(items: list[TweetQueueItem]) -> list[RoutingTweetRow]:
    # Keep the router input narrower than the persisted queue contract.
    return [
        RoutingTweetRow(
            tweet_id=item.tweet_id,
            text=item.text,
            quote_text=item.quote_text,
            image_description=item.image_description,
            url_hint=item.url_hint,
        )
        for item in items
    ]


def format_routing_result(result: RoutingResult) -> str:
    return "|".join(
        [
            ",".join(result.plain_ids),
            ",".join(result.ambiguous_ids),
            ",".join(result.image_ids),
            ",".join(result.external_ids),
        ]
    )


def _parse_group(group: str) -> list[str]:
    cleaned_group = group.strip()
    if not cleaned_group:
        return []

    short_ids = [item.strip() for item in cleaned_group.split(_ID_SEPARATOR)]
    if any(not short_id for short_id in short_ids):
        raise ValueError("Routing output contains an empty compact id.")
    return short_ids


def _normalize_field(value: str) -> str:
    return " ".join((value or "").split())
