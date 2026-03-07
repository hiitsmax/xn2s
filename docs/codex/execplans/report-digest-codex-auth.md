# Report Digest Via Codex Auth

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

This repository does not contain a checked-in `PLANS.md`; this document follows the global guidance in `~/.agents/PLANS.md`.

## Purpose / Big Picture

After this change, a user who is already logged into Codex with their ChatGPT account can run `uv run xs2n report digest` without exporting `OPENAI_API_KEY`. The visible behavior is that `xs2n report auth --status` can be used to confirm login, `xs2n report digest` will reuse the Codex-auth session stored under `~/.codex`, and the digest pipeline will generate the same markdown artifacts it does today.

## Progress

- [x] (2026-03-07 17:13Z) Confirmed the current blocker: `src/xs2n/agents/digest/llm.py` requires `OPENAI_API_KEY` and ignores Codex auth.
- [x] (2026-03-07 17:21Z) Inspected OpenClaw and verified that it reads Codex OAuth credentials from the Codex auth store instead of requiring an API key.
- [x] (2026-03-07 17:24Z) Verified locally that `~/.codex/auth.json` contains a valid ChatGPT auth session with bearer tokens.
- [x] (2026-03-07 17:31Z) Proved that the ChatGPT Codex backend accepts the local bearer token at `https://chatgpt.com/backend-api/codex/responses` and returns streaming Responses API events.
- [x] (2026-03-07 17:33Z) Proved that the same backend accepts strict JSON schema output on supported models such as `gpt-5.4`.
- [x] (2026-03-07 17:28Z) Implemented Codex-auth credential resolution plus a Responses-based `DigestLLM`.
- [x] (2026-03-07 17:29Z) Updated docs and tests for the no-API-key digest path and Codex-supported default model.
- [x] (2026-03-07 17:31Z) Re-ran the test suite (`uv run pytest`), which passed with 80 tests.
- [x] (2026-03-07 17:31Z) Completed a live Codex-auth digest run against `data/timeline.json`.

## Surprises & Discoveries

- Observation: The Codex ChatGPT backend is streaming-only for this path.
  Evidence: Direct requests to `https://chatgpt.com/backend-api/codex/responses` returned `{"detail":"Stream must be set to true"}` until `stream: true` was added.

- Observation: The Codex-auth bearer token does not have the scopes needed for normal OpenAI API model listing or generic Responses writes in this account context.
  Evidence: Direct calls to `https://api.openai.com/v1/models` and `https://api.openai.com/v1/responses` returned missing-scope errors, while the Codex backend accepted the same bearer token.

- Observation: Codex auth does not accept the old digest default model (`gpt-4.1-mini`) and also rejects `gpt-5-mini` on this backend.
  Evidence: The live Codex backend returned `The 'gpt-5-mini' model is not supported when using Codex with a ChatGPT account.` and OpenClaw’s forward-compat tests treat `openai-codex` as a GPT-5-family transport, not a generic OpenAI API replacement.

- Observation: The Codex backend enforces stricter JSON-schema rules than Pydantic emits by default.
  Evidence: Live digest runs failed until object schemas were normalized to include `additionalProperties: false` and a `required` list covering every declared property, including nullable fields.

## Decision Log

- Decision: Reuse the OpenAI Python SDK `responses.stream()` transport instead of building a raw SSE parser in this repo.
  Rationale: The SDK is already present through existing dependencies, the live prototype succeeded against the Codex backend, and this keeps the LLM wrapper mechanical.
  Date/Author: 2026-03-07 / Codex

- Decision: Keep `OPENAI_API_KEY` support as a higher-priority path, but add Codex auth as the zero-config fallback.
  Rationale: This keeps current API-key users working while enabling the user-requested ChatGPT/Codex login flow.
  Date/Author: 2026-03-07 / Codex

- Decision: Change the default digest model to a Codex-supported GPT-5 model.
  Rationale: The no-API-key path should work by default, not only after users discover a hidden compatible `--model` override.
  Date/Author: 2026-03-07 / Codex

## Outcomes & Retrospective

The digest pipeline now works end-to-end on real timeline data using Codex auth only. On this machine, `uv run xs2n report digest --timeline-file data/timeline.json --model gpt-5.4` succeeded and wrote `data/report_runs/20260307T173135Z/digest.md`. The main remaining risk is model compatibility drift on the Codex backend, so the code now raises a targeted error for unsupported models and the docs call out the Codex-supported GPT-5 requirement.

## Context and Orientation

The digest entrypoint lives in `src/xs2n/cli/report.py`. The report pipeline orchestration lives in `src/xs2n/agents/digest/pipeline.py`. The model wrapper lives in `src/xs2n/agents/digest/llm.py`, and after this change it uses the OpenAI Python SDK Responses client instead of LangChain.

In this repository, “Codex auth” means the ChatGPT login managed by the installed Codex CLI, surfaced via `uv run xs2n report auth` and stored under the user’s `~/.codex` directory. In the current local environment, `~/.codex/auth.json` contains the active auth session and bearer tokens. OpenClaw uses the same store to power its `openai-codex` provider.

The digest pipeline itself should remain unchanged. Each step module still asks `DigestLLM.run(prompt=..., payload=..., schema=...)` for a typed result. Only the transport inside `DigestLLM` should change.

## Plan of Work

First, replace the current `langchain_openai` transport in `src/xs2n/agents/digest/llm.py` with an OpenAI SDK Responses transport. Add a small credential-resolution layer that checks `OPENAI_API_KEY` first, then reads Codex auth tokens from `CODEX_HOME/auth.json` or `~/.codex/auth.json`. When the Codex path is used, point the client at `https://chatgpt.com/backend-api/codex`.

Second, keep the `DigestLLM.run(...)` signature unchanged. Convert the requested Pydantic schema into a strict JSON schema, send the prompt in `instructions`, send the payload as JSON text in a single user input item, stream the response, and parse the final JSON text back into the requested Pydantic model.

Third, update `src/xs2n/agents/digest/pipeline.py`, `README.md`, and related tests so the default model is compatible with Codex auth and the docs explain both credential paths clearly.

## Concrete Steps

From `/Users/mx/Documents/Progetti/mine/active/xs2n`, the implementation and verification flow is:

    uv run pytest tests/test_report_cli.py tests/test_report_digest.py
    uv run pytest
    uv run xs2n report auth --status
    uv run xs2n report digest --timeline-file data/timeline.json

Expected behavior after implementation:

    Logged in using ChatGPT
    Digest run <run_id>: loaded <n> threads, kept <n> threads, produced <n> issues. Saved markdown to data/report_runs/<run_id>/digest.md.

## Validation and Acceptance

Acceptance is behavioral:

1. `uv run xs2n report auth --status` reports an active ChatGPT login.
2. `uv run xs2n report digest` succeeds without `OPENAI_API_KEY` when Codex auth exists locally.
3. The run directory still contains `threads.json`, `categorized_threads.json`, `filtered_threads.json`, `processed_threads.json`, `issue_assignments.json`, `issues.json`, `run.json`, and `digest.md`.
4. `uv run pytest` passes with the new auth path covered by deterministic tests.

## Idempotence and Recovery

The change is safe to retry. If Codex auth is missing or stale, `uv run xs2n report auth` refreshes it without mutating project files. If the chosen model is unsupported on the Codex backend, the code should surface a clear runtime error that suggests a supported GPT-5 model or the API-key path.

## Artifacts and Notes

Important prototype evidence gathered before implementation:

    status= 200
    event: response.output_text.done
    data: {"type":"response.output_text.done", ... "text":"{\"answer\":\"OK\"}"}

    HTTPError
    code= 400
    {"detail":"The 'gpt-5-mini' model is not supported when using Codex with a ChatGPT account."}

## Interfaces and Dependencies

`src/xs2n/agents/digest/llm.py` must continue to export `DigestLLM` with:

    class DigestLLM:
        def __init__(self, *, model: str = DEFAULT_REPORT_MODEL, api_key: str | None = None) -> None:
            ...

        def run(self, *, prompt: str, payload: Any, schema: type[SchemaT]) -> SchemaT:
            ...

The implementation should use the `openai.OpenAI` client already available in the environment. The Codex-auth path should read the token store from `CODEX_HOME/auth.json` or `~/.codex/auth.json` and treat `tokens.access_token` as the bearer credential for `https://chatgpt.com/backend-api/codex`.

Revision note (2026-03-07): Created this plan after live verification of the Codex backend and OpenClaw’s credential-reading pattern so the implementation could proceed from a proven request shape instead of guesswork. Updated it after implementation to record the stricter JSON-schema normalization that the live Codex backend required.
