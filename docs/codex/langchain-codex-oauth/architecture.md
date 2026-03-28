# Architecture

## Why A Facade Instead Of A Separate Client API

The user goal for this package is not “talk to Codex somehow.” The goal is “keep the `ChatOpenAI` facade and change the transport only at the last mile.” That requirement drives the design.

The package therefore subclasses `langchain_openai.ChatOpenAI` rather than exposing a custom application-specific helper. This keeps the familiar LangChain surface in place for:

- `invoke`
- `ainvoke`
- `stream`
- `astream`
- `with_structured_output`
- usage inside `LangGraph`

The implementation changes where the request is prepared and where the request is sent, but it does not ask the caller to learn a new interface.

## Why The Package Is Split

The package is split into three modules because each file has one clear responsibility.

### `auth.py`

This module owns only credential lookup, refresh, and login suggestion.

It knows:

- where Codex OAuth credentials are stored
- how to decide whether a file-backed access token is close to expiry
- how to refresh that file-backed token
- how to surface a “login required” error without silently triggering an interactive flow

It does not know anything about LangChain messages or Responses payload shaping.

### `responses.py`

This module owns only the transport translation layer.

It knows:

- how to turn LangChain messages into the Codex-flavored `responses.create(...)` payload
- how to move `SystemMessage` content into top-level `instructions`
- how to rewrite tool schemas and `tool_choice` into Responses shape
- how to parse completed Responses objects and streaming events back into LangChain output objects

It does not know how credentials are found, and it does not construct OpenAI clients.

### `chat_openai.py`

This module owns only the facade class.

It knows:

- how to subclass `ChatOpenAI`
- how to install Codex-aware OpenAI clients into the inherited model object
- how to call the Responses stream for sync and async flows
- how to reuse the translation functions from `responses.py`

It does not own credential storage or low-level payload rules directly; it delegates those to the focused modules.

## Why Non-Streaming Calls Still Use The Stream Path

The Codex backend, in live traffic, rejected non-streaming Responses requests that generic clients would normally use. Because of that, the facade uses the streaming Responses path for both:

- explicit streaming calls
- plain `invoke` / `_generate`

For `invoke`, the facade collects the final completed response event from the stream and then converts that final response into a normal LangChain `ChatResult`. This preserves the caller-facing shape while respecting the backend’s actual contract.

## Default Instructions

One real edge case came from structured output. A caller using `with_structured_output(..., method="json_schema")` may pass no `SystemMessage` at all. The Codex backend still required top-level `instructions`, so the facade injects:

- `"You are a helpful assistant."`

when no explicit instruction-bearing message is present.

That fallback is narrow, but it closes a real runtime gap and keeps the package predictable for LangChain callers.
