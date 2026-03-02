# Timeline Thread Expansion With Limits

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

This repository does not contain a checked-in `PLANS.md`; this document follows the global guidance in `~/.agents/PLANS.md`.

## Purpose / Big Picture

After this change, timeline ingestion not only captures account-authored posts/replies/retweets, but also bounded thread context:
- parent-chain hydration for replies,
- recursive conversation replies,
- capped non-target-account replies.

This closes the current boundary where we had linkage IDs but not enough body/context to reconstruct full thread content.

## Progress

- [x] (2026-03-03 00:16Z) Pulled fresh Twikit Context7 docs for `Result.next()` paging and thread-related tweet detail behavior.
- [x] (2026-03-03 00:18Z) Added bounded thread expansion runtime in `src/xs2n/profile/timeline.py`.
- [x] (2026-03-03 00:19Z) Added CLI options for parent/replies/other-replies caps and wired through recovery/rate-limit flow.
- [x] (2026-03-03 00:20Z) Added/updated tests for parent-chain limit and other-author reply limit behavior.
- [x] (2026-03-03 00:22Z) Ran full `uv run pytest` suite (`59 passed`) and validated new CLI option plumbing in tests.

## Surprises & Discoveries

- Observation: `twikit.utils.Result.next()` returns an empty `Result([])` when no pagination callback exists, so reply traversal can be implemented safely with iterative `next()` calls.
  Evidence: Context7 docs for `twikit.utils.Result`.

- Observation: Missing detail tweets are common in thread traversal scenarios (deleted/private/unavailable), so tolerant handling (`NotFound`/`TweetNotAvailable`) is required to keep ingestion resilient.
  Evidence: Twikit error classes and local testing.

## Decision Log

- Decision: Enable bounded thread expansions by default with conservative caps.
  Rationale: Better downstream processing quality while limiting runaway crawl volume.
  Date/Author: 2026-03-03 / Codex

- Decision: Keep caps separately configurable (`parent`, `replies`, `other-replies`) instead of a single global limit.
  Rationale: Different data risks/performance costs require separate control.
  Date/Author: 2026-03-03 / Codex

## Outcomes & Retrospective

The ingestion layer now collects a materially richer representation of threads while remaining bounded and operator-controllable. Remaining tradeoff: we still rely on Twikit's thread/detail shape and may need adaptive guards if X internals change.
