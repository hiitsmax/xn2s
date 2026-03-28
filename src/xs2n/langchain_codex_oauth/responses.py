from __future__ import annotations

import json
from typing import Any, Iterable, Sequence

from langchain_core.messages import (
    AIMessage,
    AIMessageChunk,
    BaseMessage,
    ChatMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_core.messages.tool import tool_call, tool_call_chunk
from langchain_core.outputs import ChatGeneration, ChatGenerationChunk, ChatResult
from langchain_core.utils.function_calling import convert_to_openai_tool
from langchain_openai.chat_models.base import (
    _convert_to_openai_response_format,
    _is_pydantic_class,
)

DEFAULT_CODEX_INSTRUCTIONS = "You are a helpful assistant."


def build_codex_responses_payload(
    *,
    model: str,
    messages: Sequence[BaseMessage],
    default_params: dict[str, Any],
    kwargs: dict[str, Any],
) -> dict[str, Any]:
    """Translate LangChain chat inputs into the Codex-flavored Responses payload."""
    payload = {
        "model": model,
        **default_params,
        **kwargs,
    }
    payload["stream"] = bool(payload.get("stream", True))
    payload["store"] = False

    if "max_tokens" in payload:
        payload["max_output_tokens"] = payload.pop("max_tokens")
    if "max_completion_tokens" in payload:
        payload["max_output_tokens"] = payload.pop("max_completion_tokens")
    if payload.get("n") == 1:
        payload.pop("n")

    instructions, input_messages = split_instructions(messages)
    payload["instructions"] = instructions or DEFAULT_CODEX_INSTRUCTIONS
    payload["input"] = build_responses_input(input_messages)

    if tools := payload.pop("tools", None):
        payload["tools"] = [_flatten_tool(tool) for tool in tools]
    if tool_choice := payload.pop("tool_choice", None):
        payload["tool_choice"] = _flatten_tool_choice(tool_choice)
    if response_format := payload.pop("response_format", None):
        _apply_response_format(
            payload=payload,
            response_format=response_format,
            strict=payload.pop("strict", None),
        )
    if payload.get("extra_body"):
        payload.update(payload.pop("extra_body"))

    return payload


def split_instructions(messages: Sequence[BaseMessage]) -> tuple[str | None, list[BaseMessage]]:
    instruction_parts: list[str] = []
    input_messages: list[BaseMessage] = []
    for message in messages:
        if _is_instruction_message(message):
            text = _content_to_text(message.content)
            if text:
                instruction_parts.append(text)
        else:
            input_messages.append(message)
    instructions = "\n\n".join(part for part in instruction_parts if part).strip() or None
    return instructions, input_messages


def build_responses_input(messages: Sequence[BaseMessage]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for message in messages:
        if isinstance(message, HumanMessage):
            items.append({"role": "user", "content": _message_content(message)})
            continue
        if isinstance(message, ToolMessage):
            items.append(
                {
                    "type": "function_call_output",
                    "call_id": message.tool_call_id,
                    "output": _message_content(message),
                }
            )
            continue
        if isinstance(message, AIMessage):
            if text := _content_to_text(message.content):
                items.append({"role": "assistant", "content": text})
            for call in message.tool_calls:
                items.append(
                    {
                        "type": "function_call",
                        "name": call["name"],
                        "arguments": json.dumps(call["args"]),
                        "call_id": call["id"],
                    }
                )
            continue
        if isinstance(message, ChatMessage):
            items.append({"role": message.role, "content": _message_content(message)})
            continue
        if isinstance(message, SystemMessage):
            items.append({"role": "developer", "content": _message_content(message)})
            continue
        items.append({"role": "user", "content": _message_content(message)})
    return items


def construct_chat_result_from_response(
    *,
    response: Any,
    provider_name: str,
    schema: type | dict[str, Any] | None = None,
) -> ChatResult:
    """Turn a completed Responses object into a LangChain ChatResult."""
    response_dict = _to_dict(response)
    response_metadata = {
        "id": response_dict.get("id"),
        "model_name": response_dict.get("model"),
        "model_provider": provider_name,
    }

    text_parts: list[str] = []
    tool_calls = []
    additional_kwargs: dict[str, Any] = {}
    for output in response_dict.get("output", []):
        output_type = output.get("type")
        if output_type == "message":
            for content in output.get("content", []):
                if content.get("type") == "output_text":
                    text = content.get("text")
                    if isinstance(text, str):
                        text_parts.append(text)
                elif content.get("type") == "refusal":
                    additional_kwargs["refusal"] = content.get("refusal")
        elif output_type == "function_call":
            arguments = output.get("arguments") or "{}"
            try:
                parsed_arguments = json.loads(arguments)
            except json.JSONDecodeError:
                parsed_arguments = {"__raw__": arguments}
            tool_calls.append(
                tool_call(
                    name=output.get("name") or "",
                    args=parsed_arguments,
                    id=output.get("call_id"),
                )
            )
        else:
            continue

    text = "".join(text_parts)
    if schema is not None and text:
        parsed = _parse_text_with_schema(text=text, schema=schema)
        if parsed is not None:
            additional_kwargs["parsed"] = parsed

    message = AIMessage(
        content=text,
        tool_calls=tool_calls,
        additional_kwargs=additional_kwargs,
        response_metadata={k: v for k, v in response_metadata.items() if v is not None},
        id=response_dict.get("id"),
    )
    return ChatResult(generations=[ChatGeneration(message=message)])


def convert_responses_event_to_chunk(
    *,
    event: Any,
) -> ChatGenerationChunk | None:
    """Translate streaming Responses events into LangChain chunks."""
    event_dict = _to_dict(event)
    event_type = event_dict.get("type")
    if event_type == "response.output_text.delta":
        return ChatGenerationChunk(message=AIMessageChunk(content=event_dict.get("delta", "")))
    if event_type == "response.output_item.added":
        item = _to_dict(event_dict.get("item", {}))
        if item.get("type") == "function_call":
            return ChatGenerationChunk(
                message=AIMessageChunk(
                    content="",
                    tool_call_chunks=[
                        tool_call_chunk(
                            name=item.get("name"),
                            args=item.get("arguments"),
                            id=item.get("call_id"),
                            index=0,
                        )
                    ],
                )
            )
    if event_type == "response.function_call_arguments.delta":
        return ChatGenerationChunk(
            message=AIMessageChunk(
                content="",
                tool_call_chunks=[
                    tool_call_chunk(
                        name=None,
                        args=event_dict.get("delta"),
                        id=None,
                        index=0,
                    )
                ],
            )
        )
    return None


def extract_completed_response(event: Any) -> Any | None:
    event_dict = _to_dict(event)
    if event_dict.get("type") in {"response.completed", "response.incomplete"}:
        return event_dict.get("response")
    return None


def _apply_response_format(
    *,
    payload: dict[str, Any],
    response_format: Any,
    strict: Any,
) -> None:
    if _is_pydantic_class(response_format):
        schema_dict = response_format.model_json_schema()
        strict = True if strict is None else strict
    else:
        schema_dict = response_format

    if schema_dict == {"type": "json_object"}:
        payload["text"] = {"format": {"type": "json_object"}}
        return

    formatted = _convert_to_openai_response_format(schema_dict, strict=strict)
    if (
        isinstance(formatted, dict)
        and formatted.get("type") == "json_schema"
        and isinstance(formatted.get("json_schema"), dict)
    ):
        payload["text"] = {
            "format": {
                "type": "json_schema",
                **formatted["json_schema"],
            }
        }


def _flatten_tool(tool: Any) -> dict[str, Any]:
    if isinstance(tool, type):
        tool = convert_to_openai_tool(tool)
    if isinstance(tool, dict) and tool.get("type") == "function" and "function" in tool:
        return {"type": "function", **tool["function"]}
    return tool


def _flatten_tool_choice(tool_choice: Any) -> Any:
    if (
        isinstance(tool_choice, dict)
        and tool_choice.get("type") == "function"
        and isinstance(tool_choice.get("function"), dict)
    ):
        return {"type": "function", **tool_choice["function"]}
    return tool_choice


def _is_instruction_message(message: BaseMessage) -> bool:
    return isinstance(message, SystemMessage) or (
        isinstance(message, ChatMessage) and message.role == "developer"
    )


def _message_content(message: BaseMessage) -> Any:
    if isinstance(message.content, list):
        return message.content
    return _content_to_text(message.content)


def _content_to_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
                continue
            if isinstance(block, dict):
                if block.get("type") in {"text", "input_text", "output_text"}:
                    text = block.get("text")
                    if isinstance(text, str):
                        parts.append(text)
                        continue
                value = block.get("value")
                if isinstance(value, str):
                    parts.append(value)
        return "".join(parts)
    return str(content)


def _parse_text_with_schema(*, text: str, schema: type | dict[str, Any]) -> Any | None:
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return None
    if _is_pydantic_class(schema):
        return schema.model_validate(parsed)
    return parsed


def _to_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if hasattr(value, "model_dump"):
        return value.model_dump(exclude_none=True, mode="json")
    if hasattr(value, "__dict__"):
        return {
            key: _to_dict(item) if isinstance(item, dict | list) else item
            for key, item in value.__dict__.items()
            if not key.startswith("_")
        }
    raise TypeError(f"Cannot convert value of type {type(value)!r} to dict.")
