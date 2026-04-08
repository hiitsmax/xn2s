# Text Router Agent ExecPlan

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

This repository follows `/Users/mx/.agents/PLANS.md`; this document must be maintained in accordance with that file.

## Purpose / Big Picture

After this change, `xs2n` will have a dedicated routing agent that classifies a batch of tweets into four strict categories: plain text, ambiguous, images, and external links. The routing input is optimized for token use by packing each tweet into one line with a short local identifier, and the routing output is a single strict string with four pipe-separated groups. We are only implementing the text router now, but its input contract already includes an `imgdesc` field so a future image-description agent can run first and feed its result into this router.

## Progress

- [x] (2026-04-08 09:30Z) Explored the existing runner, base agent, prompt loader, schemas, and tests to find the smallest honest extension point.
- [x] (2026-04-08 09:40Z) Confirmed current OpenAI guidance for concise GPT-5 routing work: low reasoning effort, low verbosity, and explicit output contracts.
- [x] (2026-04-08 10:05Z) Added failing tests for compact ids, single-line batch formatting, strict route parsing, richer queue items, and the new router agent path in `run.py`.
- [x] (2026-04-08 10:20Z) Implemented `text_router_agent`, compact routing helpers, prompt contract, queue-field widening, and CLI `--route-text` mode.
- [x] (2026-04-08 10:28Z) Ran the full pytest suite, updated `docs/codex/autolearning.md`, and recorded outcomes.

## Surprises & Discoveries

- Observation: The current queue item schema does not carry image metadata, so the router cannot infer media directly from repository state today.
  Evidence: `src/xs2n/schemas/clustering.py` only stores `tweet_id`, `account_handle`, `text`, `url`, `created_at`, `status`, `cluster_id`, and `processing_note`.

- Observation: The installed `agents.ModelSettings` already supports `verbosity`, so we can keep compact output behavior in model settings instead of relying on prompt wording alone.
  Evidence: `uv run python - <<'PY' ... inspect.signature(ModelSettings) ... PY` showed `verbosity: Literal['low', 'medium', 'high'] | None`.

- Observation: The plan reviewer was right that helper-only work would not satisfy the “observable behavior” bar, so the change needed a CLI path and a persisted queue contract update, not just unit-tested modules.
  Evidence: `src/xs2n/run.py` originally only built the base scaffold, and `src/xs2n/schemas/clustering.py` originally lacked `quote_text`, `image_description`, and `url_hint`.

## Decision Log

- Decision: Extend the existing `BaseAgent` path instead of creating a new runtime abstraction layer.
  Rationale: The repository intentionally favors direct, honest orchestration and thin wrappers. A new runtime layer would add naming and indirection without solving a real problem yet.
  Date/Author: 2026-04-08 / Codex

- Decision: Encode tweet ids locally and pass only short ids to the model.
  Rationale: The user explicitly wants token optimization, and short ids reduce repeated token cost in both the packed batch input and the strict grouped output.
  Date/Author: 2026-04-08 / Codex

- Decision: Keep the router output as a plain string instead of JSON.
  Rationale: The user wants the most compact possible transport, and a fixed `plain|ambiguous|images|external` contract is easy to validate locally.
  Date/Author: 2026-04-08 / Codex

- Decision: Add an explicit CLI mode instead of replacing the scaffold default path.
  Rationale: The repository still uses the base scaffold as its main default runtime, but the new router needed an observable path now. `--route-text` makes the feature testable without breaking the existing default behavior.
  Date/Author: 2026-04-08 / Codex

- Decision: Widen `TweetQueueItem` additively with neutral routing fields.
  Rationale: The router consumes queue items today, so the data contract needed to carry quote text and future image-derived text without inventing hidden prompt behavior.
  Date/Author: 2026-04-08 / Codex

## Outcomes & Retrospective

The repository now has a dedicated `text_router_agent` that batches one-line tweet rows with compact local ids, routes them through a strict prompt contract, and validates the grouped output before returning original tweet ids. The CLI gained a `--route-text` mode so the new path is visible and testable without replacing the existing scaffold default. The persisted queue contract was widened with `quote_text`, `image_description`, and `url_hint` so the routing path can evolve toward the future image-description stage without a silent schema gap.

What remains is the upstream enrichment work: the fetch layer still does not populate image descriptions, and external-link detection is only as strong as the queue data it receives. Those are the right next milestones after this first router increment.

## Context and Orientation

The active runtime is small by design. `src/xs2n/run.py` is the current CLI entrypoint. `src/xs2n/agents/base_agent.py` holds a thin OpenAI Agents SDK wrapper that loads instructions from `src/xs2n/prompts/` and uses Codex/OpenAI auth from `src/xs2n/utils/auth/openai_client.py`. Shared tweet contracts live in `src/xs2n/schemas/`. Existing tests for the current agent live in `tests/test_base_agent.py`.

For this feature, we need one new agent and a few neutral helpers. “Strict output” means the model must emit exactly one line with exactly four groups separated by `|`, and each group contains zero or more compact ids separated by `,`. The group order is fixed: `plain|ambiguous|images|external`.

## Plan of Work

First, add shared router contracts under `src/xs2n/schemas/`. These models should describe one tweet routing row, one batch payload, and the validated route result. The routing row should contain the original tweet id plus the fields that can reach the model on one packed line: main text, quoted text, image description, and a compact link hint.

Next, add a focused helper module that owns three responsibilities only: compact id encoding/decoding, one-line batch formatting, and strict route parsing. The compact id encoder should use a printable ASCII alphabet chosen to avoid the separators used by the batch transport. The formatter should escape or normalize newlines so one tweet always becomes one line. The parser should reject malformed output early: wrong number of groups, unknown ids, duplicates, or ids appearing in more than one group.

Then extend the agent layer with a small reusable base constructor so new single-purpose agents can share the same OpenAI/Codex auth and tracing path without copying the Runner setup. Add a concrete text router agent that loads a dedicated prompt and applies `reasoning={"effort": "low"}` plus `verbosity="low"`.

Finally, add tests first for the helper behaviors and the router agent wiring, then implement the minimum code to make them pass. Update `docs/codex/autolearning.md` with the new learning from this branch once the implementation is proven.

## Concrete Steps

From `/Users/mx/Documents/Progetti/mine/active/xs2n`, run the focused test file after each small change:

    uv run pytest tests/test_text_router_agent.py -q

When the agent wiring is in place, also run:

    uv run pytest tests/test_base_agent.py tests/test_text_router_agent.py -q

Expected final transcript:

    .......
    7 passed in <time>s

## Validation and Acceptance

Acceptance is behavior, not just file presence:

1. `tests/test_text_router_agent.py` must prove that compact ids are short, reversible, and avoid transport separators.
2. The tests must prove that one routing row becomes one packed line and that the parser accepts only a four-group strict output string.
3. The router agent test must prove that the new agent loads its prompt, uses the shared OpenAI Responses model path, and applies low reasoning plus low verbosity.
4. Existing `tests/test_base_agent.py` must still pass, proving that the extension did not break the existing scaffold.

## Idempotence and Recovery

This plan is additive. Re-running the tests is safe. If the strict parser rejects a model output during development, fix the prompt or helper and rerun the focused tests. No destructive migrations or data rewrites are involved.

## Artifacts and Notes

Key repository files for this task:

- `src/xs2n/agents/base_agent.py`
- `src/xs2n/agents/text_router_agent.py`
- `src/xs2n/agents/__init__.py`
- `src/xs2n/prompts/manager.py`
- `src/xs2n/prompts/text_router_agent_prompt.txt`
- `src/xs2n/schemas/clustering.py`
- `src/xs2n/schemas/routing.py`
- `src/xs2n/utils/text_router.py`
- `src/xs2n/run.py`
- `tests/test_base_agent.py`
- `tests/test_text_router_agent.py`

Plan revision note: Updated on 2026-04-08 after implementation to record the CLI routing path, the widened queue contract, and the full-suite verification results.
