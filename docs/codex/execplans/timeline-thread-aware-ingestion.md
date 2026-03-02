# Timeline Thread-Aware Ingestion

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

This repository does not contain a checked-in `PLANS.md`; this document follows the global guidance in `~/.agents/PLANS.md`.

## Purpose / Big Picture

After this change, `xs2n timeline` captures full account-authored thread activity by including replies (not only top-level posts/retweets), and persists reply linkage metadata so downstream processing can reconstruct thread structure.

## Progress

- [x] (2026-03-02 23:58Z) Pulled fresh Twikit docs from Context7 for `User.get_tweets('Replies')`, `Tweet.in_reply_to`, and tweet detail/thread metadata.
- [x] (2026-03-03 00:00Z) Refactored timeline fetcher to ingest both `Tweets` and `Replies` feeds with cross-feed dedupe and final ordering.
- [x] (2026-03-03 00:01Z) Added reply/thread metadata to timeline entries (`in_reply_to_tweet_id`, `conversation_id`, `timeline_source`).
- [x] (2026-03-03 00:02Z) Updated timeline persistence layer and unit tests for reply-aware behavior.
- [x] (2026-03-03 00:04Z) Ran full test suite and validated command messaging updates for reply-aware ingest.

## Surprises & Discoveries

- Observation: Twikit exposes replies as a first-class timeline type (`get_tweets('Replies')`), so we can capture thread continuations without expensive per-tweet detail lookups.
  Evidence: Context7 docs for Twikit `User.get_tweets`.

- Observation: Conversation ids are not always guaranteed as a documented top-level Tweet property, but can appear in tweet legacy payloads.
  Evidence: Context7 Tweet class docs plus existing runtime-safe fallback design.

## Decision Log

- Decision: Expand ingestion to `Tweets` + `Replies` by default.
  Rationale: The product goal is full thread coverage from account activity; opt-in flags would keep the old gap.
  Date/Author: 2026-03-03 / Codex

- Decision: Persist thread linkage metadata in flat timeline entries instead of nested thread documents.
  Rationale: Keeps storage append/dedupe behavior unchanged and lets processing agents reconstruct threads deterministically.
  Date/Author: 2026-03-03 / Codex

## Outcomes & Retrospective

Thread-awareness is now implemented in the ingestion layer while preserving the same CLI ergonomics and dedupe semantics. The main remaining tradeoff is that this does not yet hydrate full parent-context tweets for each reply; downstream processing can either infer context from stored linkage ids or add optional tweet-detail expansion later.
