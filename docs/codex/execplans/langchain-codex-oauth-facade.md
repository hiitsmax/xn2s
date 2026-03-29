# LangChain Codex OAuth Facade

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

This repository does not contain a checked-in `PLANS.md`; this document follows the global guidance in `~/.agents/PLANS.md` and must be maintained in accordance with it.

## Purpose / Big Picture

After this change, a developer using this repository can instantiate a `ChatOpenAI`-compatible model facade that reads Codex OAuth credentials before asking for login, speaks to the Codex backend instead of the standard OpenAI API-key path, and can be passed directly into LangGraph or any other code that expects the public `ChatOpenAI` surface. The feature is observable by running a focused pytest suite and a smoke script that shows the new facade building Codex-style `responses.create(...)` payloads from ordinary LangChain messages.

## Progress

- [x] (2026-03-28 15:02Z) Confirmed the target branch state and switched to `Langchain-DPagenz` for isolated implementation.
- [x] (2026-03-28 15:06Z) Verified the local `langchain-openai` package version and located the real `ChatOpenAI` request construction path in site-packages.
- [x] (2026-03-28 15:09Z) Confirmed the current repo credential resolver already reads Codex OAuth tokens from `CODEX_HOME` and the macOS keychain.
- [x] (2026-03-28 16:18Z) Wrote failing tests for payload shaping, login-required behavior, file-token refresh, simple invoke, structured output, and tool-call parsing.
- [x] (2026-03-28 16:34Z) Implemented the narrow-scoped facade package under `src/xs2n/langchain_codex_oauth/` with separate `auth.py`, `responses.py`, and `chat_openai.py` modules.
- [x] (2026-03-28 16:42Z) Added repository docs in `docs/codex/langchain-codex-oauth.md`, updated `docs/codex/autolearning.md`, and ran focused verification plus live smoke checks.

## Surprises & Discoveries

- Observation: The installed local `langchain-openai` version is `0.2.8`, and its `ChatOpenAI` implementation is still wired to `chat.completions` rather than to the newer Responses-native path described in current LangChain docs.
  Evidence: `python - <<'PY' ... import importlib.metadata as m; print(m.version('langchain-openai')) ... PY` returned `0.2.8`, and `/Library/Frameworks/Python.framework/Versions/3.12/lib/python3.12/site-packages/langchain_openai/chat_models/base.py` shows `self.client = self.root_client.chat.completions`.
- Observation: The Codex backend rejects standard OpenAI/LangChain payload defaults and requires a more specific request contract.
  Evidence: live smoke tests against `https://chatgpt.com/backend-api/codex` returned `400` errors including `Input must be a list`, `Store must be set to false`, `Stream must be set to true`, and `Instructions are required`.
- Observation: `with_structured_output(..., method="json_schema")` still fails against the Codex backend when no `SystemMessage` is present, unless the facade injects a default top-level instruction.
  Evidence: the first live structured-output smoke failed with `400 - {'detail': 'Instructions are required'}`; after adding the fallback instruction, the same smoke returned `{"status":"LIVE_STRUCTURED_OK"}`.
- Observation: The installed Codex CLI binary exposes enough public strings to confirm the refresh token URL and public client id used for OAuth refresh.
  Evidence: `strings /opt/homebrew/Caskroom/codex/0.114.0/codex-aarch64-apple-darwin | rg "oauth/token|client_id|refresh_token"` returned `https://auth.openai.com/oauth/token` and `app_EMoamEEZ73f0CkXaXp7hrann`.

## Decision Log

- Decision: Build a `ChatOpenAI`-compatible facade rather than a project-specific helper.
  Rationale: The user wants to swap the object directly into LangGraph, so the public surface must match `ChatOpenAI` as closely as possible.
  Date/Author: 2026-03-28 / Codex
- Decision: Keep the new implementation in an explicit package under `src/xs2n/` instead of modifying `src/xs2n/agents/llm.py`.
  Rationale: The cluster builder runner should stay narrow and honest about its job, while the LangChain-compatible provider belongs in its own focused folder with separate docs and tests.
  Date/Author: 2026-03-28 / Codex
- Decision: The facade must first try existing Codex OAuth credentials and only suggest login when no usable credentials are present.
  Rationale: This matches the requested UX and keeps the runtime predictable for automation and cron-style use.
  Date/Author: 2026-03-28 / Codex
- Decision: Use the Responses streaming path for both streaming and non-streaming facade calls.
  Rationale: The Codex backend currently rejects non-streaming Responses calls, so `_generate` and `_agenerate` collect the final completed response from the stream instead of using a separate non-stream endpoint.
  Date/Author: 2026-03-28 / Codex
- Decision: Refresh only file-backed OAuth documents in `v1`.
  Rationale: The file path can be updated safely in place, while keychain-backed credentials would require a second state-writing implementation that is outside this narrow-scoped provider package.
  Date/Author: 2026-03-28 / Codex

## Outcomes & Retrospective

The repository now contains an additive package at `src/xs2n/langchain_codex_oauth/` that exports `ChatOpenAICodexOAuth`, a `ChatOpenAI`-compatible facade for Codex OAuth. Focused tests cover payload shaping, fallback instructions, tool schema rewriting, file-backed refresh, login-required errors, simple invoke, structured output, and function-call parsing. Live smoke tests confirmed that the facade can execute a plain `invoke()` and a `with_structured_output(..., method="json_schema")` call against the real Codex backend using the current local login state.

The remaining limitation is intentional scope: the refresh implementation updates only file-backed Codex auth documents, while keychain-backed credentials are reused without in-place refresh.

## Context and Orientation

The current repository is a minimal Python package rooted at `src/xs2n`. The existing model credential logic lives in `src/xs2n/credentials.py`; it already knows how to locate a Codex OAuth access token from `CODEX_HOME/auth.json` or the macOS keychain. The cluster builder runtime lives in `src/xs2n/cluster_builder/` and needs a LangChain-compatible model surface for the deep-agent runtime. The focused tests that demonstrate repository style live in `tests/test_codex_auth.py` and `tests/test_langchain_codex_oauth.py`.

For this plan, “facade” means a class that looks like `langchain_openai.ChatOpenAI` to the rest of the application, even though its request transport is specialized for the Codex backend. “Codex OAuth” means the ChatGPT/Codex sign-in flow that yields an access token and Codex-specific base URL, not an `OPENAI_API_KEY`.

The implementation should stay narrow. Create a new explicit folder that holds only the Codex OAuth provider logic and the `ChatOpenAI`-compatible facade. Do not rename the existing digest runtime into something more generic; the new provider package is additive.

## Plan of Work

Start with tests. Add a focused test module that defines the behavior the new facade must preserve: when given LangChain `SystemMessage` and `HumanMessage` input, it must produce a Codex-compatible Responses payload with top-level `instructions`, list-based `input`, and Codex-required request flags. Add a credential test that proves the provider first reuses the current resolver behavior before surfacing a login-required error. Add a smoke-style unit test that proves the facade can be instantiated with `auth_mode="codex_oauth"` and exposes the same sync and async generation entry points expected by LangGraph.

With the failing tests in place, add a new package under `src/xs2n/` for the provider. Put the credential access and login recommendation logic in one module, put the payload translation logic in another module, and put the `ChatOpenAI`-compatible facade class in its own module. The facade should subclass `langchain_openai.ChatOpenAI` so the public shape remains familiar, but it should override the environment setup and generation methods so it talks to `openai.OpenAI().responses` rather than to `chat.completions`. Keep the conversion rules explicit and small: collect all `SystemMessage` content into `instructions`, convert the remaining messages into `input`, set `store=False`, and ensure the stream methods always call the backend with `stream=True`.

After the provider code exists, document it in a repository-local Markdown file under `docs/codex/` and update `docs/codex/autolearning.md` with the key lessons from the work. The documentation must explain what this package is for, what it intentionally does not do, how it finds credentials, and how to pass it into LangGraph.

## Concrete Steps

Work from `/Users/mx/Documents/Progetti/mine/active/xs2n`.

1. Write and run the new failing tests.

    `uv run pytest tests/test_langchain_codex_oauth.py -q`

    Expected before implementation: one or more failures showing that the new provider package or facade class does not exist yet.

2. Implement the provider package and rerun the focused tests after each small change.

    `uv run pytest tests/test_langchain_codex_oauth.py -q`

    Expected after implementation: all tests in that file pass.

3. Run the existing focused tests that cover the shared credential surface.

    `uv run pytest tests/test_codex_auth.py tests/test_langchain_codex_oauth.py -q`

    Expected: all tests pass, proving the additive package did not break the existing auth support.

4. Run a narrow smoke script that instantiates the new facade and prints the translated request payload without making a live network request.

    `uv run python - <<'PY'`
    `from xs2n.langchain_codex_oauth import ChatOpenAICodexOAuth`
    `from langchain_core.messages import SystemMessage, HumanMessage`
    `llm = ChatOpenAICodexOAuth(model="gpt-5.4-mini", auth_mode="codex_oauth")`
    `payload = llm._build_codex_responses_payload([SystemMessage("You are terse."), HumanMessage("ping")])`
    `print(payload)`
    `PY`

    Expected output excerpt:

        {'model': 'gpt-5.4-mini', 'instructions': 'You are terse.', 'input': [{'role': 'user', 'content': 'ping'}], 'store': False, ...}

Actual verification performed during implementation:

    uv run --extra langchain pytest tests/test_langchain_codex_oauth.py -q
    # 8 passed in 0.42s

    uv run pytest tests/test_codex_auth.py tests/test_langchain_codex_oauth.py -q
    # 10 passed in 1.15s

    uv run --extra langchain python - <<'PY'
    from langchain_core.messages import HumanMessage, SystemMessage
    from xs2n.langchain_codex_oauth import ChatOpenAICodexOAuth
    llm = ChatOpenAICodexOAuth(model='gpt-5.4-mini', auth_mode='codex_oauth')
    result = llm.invoke([
        SystemMessage('Reply with exactly LIVE_SMOKE_OK and nothing else.'),
        HumanMessage('Reply now.'),
    ])
    print(result.content)
    PY
    # LIVE_SMOKE_OK

    uv run --extra langchain python - <<'PY'
    from langchain_core.messages import HumanMessage
    from pydantic import BaseModel
    from xs2n.langchain_codex_oauth import ChatOpenAICodexOAuth
    class SmokeResult(BaseModel):
        status: str
    llm = ChatOpenAICodexOAuth(model='gpt-5.4-mini', auth_mode='codex_oauth')
    result = llm.with_structured_output(SmokeResult, method='json_schema').invoke([
        HumanMessage('Return JSON with status set to LIVE_STRUCTURED_OK.')
    ])
    print(result.model_dump_json())
    PY
    # {"status":"LIVE_STRUCTURED_OK"}

    uv run --extra langchain --with langchain --with langgraph python - <<'PY'
    from langchain.agents import create_agent
    from xs2n.langchain_codex_oauth import ChatOpenAICodexOAuth
    llm = ChatOpenAICodexOAuth(model='gpt-5.4-mini', auth_mode='codex_oauth')
    agent = create_agent(
        llm,
        tools=[],
        system_prompt='Reply with exactly LANGGRAPH_FINAL_OK and nothing else.',
    )
    result = agent.invoke({'messages': [{'role': 'user', 'content': 'Reply now.'}]})
    print(result['messages'][-1].content)
    PY
    # LANGGRAPH_FINAL_OK

## Validation and Acceptance

Acceptance is behavioral. A developer must be able to import the new facade from the new package, instantiate it with `auth_mode="codex_oauth"`, and hand it ordinary LangChain messages without manually shaping Codex payloads. The focused pytest file must fail before the package exists and pass after the implementation. The credential tests must continue to pass. The smoke script must show that the new facade translates a LangChain conversation into the Codex request shape with `instructions`, list-based `input`, and disabled server-side storage.

## Idempotence and Recovery

This work is additive. Re-running the tests is safe. If the smoke script or tests fail halfway through development, return to the latest passing pytest command and continue from there. If the branch needs to be recreated, the plan, docs, and tests in this repository are the source of truth for restarting.

## Artifacts and Notes

Important evidence gathered before implementation:

    langchain-openai 0.2.8
    langchain 0.3.7
    langgraph 0.2.45
    openai 2.29.0

    CREDENTIAL_SOURCE=codex_auth_file
    BASE_URL=https://chatgpt.com/backend-api/codex
    OPENAI_RESPONSES_ERROR=BadRequestError: Error code: 400 - {'detail': 'Store must be set to false'}
    LC_STRING_ERROR=BadRequestError: Error code: 400 - {'detail': 'Instructions are required'}

## Interfaces and Dependencies

Use the existing `openai` Python package already present in this repository, plus `langchain-openai` and `langchain-core` as the compatibility target for the facade. The new package should export one public class and a small credential helper surface:

    xs2n.langchain_codex_oauth.ChatOpenAICodexOAuth

The facade must accept:

    ChatOpenAICodexOAuth(
        model: str,
        auth_mode: Literal["codex_oauth"] = "codex_oauth",
        ...
    )

The facade must expose the normal `ChatOpenAI` invocation methods through inheritance. It must also define one small internal helper that is easy to test directly:

    def _build_codex_responses_payload(
        self,
        messages: list[BaseMessage],
        *,
        stop: list[str] | None = None,
        stream: bool | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:

At the end of the milestone, the repository should contain a documented, narrow-scoped provider package that a LangGraph caller can swap in where they would normally use `ChatOpenAI`.

Revision note (2026-03-28): Initial ExecPlan created after design approval to capture the additive provider package approach, the known Codex backend constraints, and the verification strategy before implementation.
