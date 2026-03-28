# LangChain Codex OAuth Facade

This folder documents the narrow-scoped package in `src/xs2n/langchain_codex_oauth/`.

The package exists for one job only: expose a `ChatOpenAI`-compatible facade that can be swapped into `LangGraph` while authenticating through Codex / ChatGPT OAuth instead of `OPENAI_API_KEY`.

The public entry point is:

- `xs2n.langchain_codex_oauth.ChatOpenAICodexOAuth`

This is not a generic OpenAI provider abstraction. It is an additive compatibility layer for one specific transport problem: the Codex backend accepts a stricter Responses payload than the generic `ChatOpenAI` wrapper sends by default.

## Navigation

- [architecture.md](/Users/mx/Documents/Progetti/mine/active/xs2n/docs/codex/langchain-codex-oauth/architecture.md)
  What the facade is, how the package is split, and why the implementation subclasses `ChatOpenAI`.
- [auth-and-refresh.md](/Users/mx/Documents/Progetti/mine/active/xs2n/docs/codex/langchain-codex-oauth/auth-and-refresh.md)
  How credentials are discovered, when refresh is attempted, and when login is suggested.
- [usage.md](/Users/mx/Documents/Progetti/mine/active/xs2n/docs/codex/langchain-codex-oauth/usage.md)
  Installation, imports, simple invoke, structured output, and LangGraph examples.
- [verification-and-limits.md](/Users/mx/Documents/Progetti/mine/active/xs2n/docs/codex/langchain-codex-oauth/verification-and-limits.md)
  What was tested for real, what is covered by pytest, and the current limits of the package.

## Quick Summary

The Codex backend required all of these behaviors during live smoke tests:

- top-level `instructions`
- `input` as a list
- `store=False`
- `stream=True`

The facade keeps the public LangChain calling shape familiar and moves those Codex-specific rules into one explicit package.

## Package Layout

- `src/xs2n/langchain_codex_oauth/auth.py`
  Reads existing Codex OAuth credentials, refreshes file-backed tokens when possible, and exposes the login helper.
- `src/xs2n/langchain_codex_oauth/responses.py`
  Converts LangChain messages into the Codex-flavored `responses.create(...)` payload and converts completed responses or streaming events back into LangChain objects.
- `src/xs2n/langchain_codex_oauth/chat_openai.py`
  The `ChatOpenAI`-compatible facade itself.

## Install

The base repository stays minimal. Install the LangChain facade only when you need it:

```bash
uv sync --extra langchain
```

## Design Boundary

This package is intentionally additive. It does not replace the digest CLI wrapper in `src/xs2n/agents/llm.py`, and it does not try to become a full provider framework. The goal is a thin, honest package whose name matches what it really does today.
