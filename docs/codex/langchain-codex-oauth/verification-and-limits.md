# Verification And Limits

## Focused Test Coverage

The pytest coverage for this facade currently lives in [test_langchain_codex_oauth.py](/Users/mx/Documents/Progetti/mine/active/xs2n/tests/test_langchain_codex_oauth.py).

That file covers:

- `SystemMessage` to `instructions` translation
- default instructions when no system prompt is present
- tool schema rewriting into Responses shape
- `tool_choice` rewriting
- structured output payload formatting
- file-backed token refresh
- guided login-required failure
- plain `invoke()` through the Responses stream
- structured output parsing
- function-call parsing into LangChain tool calls

## Verified Commands

The following commands were run after the facade implementation existed:

```bash
uv run --extra langchain pytest tests/test_langchain_codex_oauth.py tests/test_codex_auth.py tests/test_llm.py -q
```

Observed result:

- `11 passed`

Live smoke checks were also run against the real Codex backend using the current local login state.

### Plain invoke

Observed result:

- `FINAL_LIVE_SMOKE_OK`

### Structured output

Observed result:

- `{"status":"FINAL_STRUCTURED_OK"}`

### LangGraph integration

Observed result:

- `LANGGRAPH_FINAL_OK`

## Current Limits

### File-backed refresh only

The refresh path updates only `CODEX_HOME/auth.json`. Keychain-backed credentials are reused as-is.

### Targeted to the installed LangChain surface

The package is aimed at the repository’s current `langchain-openai` shape rather than trying to mirror every behavior of newer releases. It is intentionally narrow and pragmatic.

### Codex-specific contract

The package is only for the Codex / ChatGPT OAuth path. It is not a universal provider adapter and does not attempt to normalize arbitrary OpenAI-compatible backends.

### Stream-first assumption

The implementation currently uses the Responses stream path for both streaming and non-streaming caller surfaces because that is what the live Codex backend accepted during verification.
