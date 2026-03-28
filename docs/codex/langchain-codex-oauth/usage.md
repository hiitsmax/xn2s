# Usage

## Install

```bash
uv sync --extra langchain
```

## Basic Construction

```python
from xs2n.langchain_codex_oauth import ChatOpenAICodexOAuth

llm = ChatOpenAICodexOAuth(
    model="gpt-5.4-mini",
    auth_mode="codex_oauth",
)
```

The explicit `auth_mode="codex_oauth"` keeps the surface narrow and honest. This facade is not pretending to support multiple unrelated auth systems.

## Plain `invoke`

```python
from langchain_core.messages import HumanMessage, SystemMessage

result = llm.invoke(
    [
        SystemMessage("Reply with exactly OK and nothing else."),
        HumanMessage("Reply now."),
    ]
)

print(result.content)
```

What happens internally:

- `SystemMessage` content becomes top-level `instructions`
- user messages become list-based `input`
- the request is sent through the Codex Responses stream
- the final completed response is converted back into a normal LangChain `AIMessage`

## Structured Output

```python
from langchain_core.messages import HumanMessage
from pydantic import BaseModel

class DigestResult(BaseModel):
    status: str

structured = llm.with_structured_output(
    DigestResult,
    method="json_schema",
)

result = structured.invoke(
    [HumanMessage("Return JSON with status set to READY.")]
)

print(result.status)
```

If no `SystemMessage` is present, the facade injects a small default instruction so the Codex backend still receives the top-level `instructions` field it requires.

## LangGraph Drop-In

```python
from langchain.agents import create_agent
from xs2n.langchain_codex_oauth import ChatOpenAICodexOAuth

llm = ChatOpenAICodexOAuth(
    model="gpt-5.4-mini",
    auth_mode="codex_oauth",
)

agent = create_agent(
    llm,
    tools=[],
    system_prompt="Reply with exactly LANGGRAPH_OK and nothing else.",
)

result = agent.invoke(
    {"messages": [{"role": "user", "content": "Reply now."}]}
)

print(result["messages"][-1].content)
```

This is the main compatibility target: keep the caller-facing shape that LangGraph expects while swapping only the transport details.

## Manual Login Helper

If no usable credentials are present:

```python
from xs2n.langchain_codex_oauth import run_codex_oauth_login

run_codex_oauth_login()
```

The package deliberately suggests login instead of running it automatically during object construction.
