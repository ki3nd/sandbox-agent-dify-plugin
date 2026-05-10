"""Converter between Dify PromptMessage and JSON-serializable dicts."""

import json
from typing import Any

from dify_plugin.entities.model.message import (
    AssistantPromptMessage,
    PromptMessage,
    ToolPromptMessage,
    UserPromptMessage,
)

from history.models import Turn, TurnMessage


def prompt_message_to_dict(msg: PromptMessage) -> dict[str, Any]:
    """Convert a Dify PromptMessage to JSON-serializable dict.
    
    Args:
        msg: Dify PromptMessage (AssistantPromptMessage, ToolPromptMessage, etc.)
        
    Returns:
        Dict with role, content, and optional tool_calls/tool_call_id/name
    """
    if isinstance(msg, AssistantPromptMessage):
        d: dict[str, Any] = {
            "role": "assistant",
            "content": _extract_content(msg.content),
        }
        if msg.tool_calls:
            d["tool_calls"] = [
                {
                    "id": tc.id,
                    "name": tc.function.name,
                    "arguments": _parse_arguments(tc.function.arguments),
                }
                for tc in msg.tool_calls
            ]
        return d
    
    elif isinstance(msg, ToolPromptMessage):
        return {
            "role": "tool",
            "content": _extract_content(msg.content),
            "tool_call_id": msg.tool_call_id,
            "name": msg.name,
        }
    
    elif isinstance(msg, UserPromptMessage):
        return {
            "role": "user",
            "content": _extract_content(msg.content),
        }
    
    else:
        # Fallback for other message types
        return {
            "role": "unknown",
            "content": str(msg.content) if msg.content else "",
        }


def dict_to_prompt_message(d: dict[str, Any]) -> PromptMessage:
    """Convert a dict back to Dify PromptMessage.
    
    Args:
        d: Dict with role, content, and optional fields
        
    Returns:
        Appropriate PromptMessage subclass
    """
    role = d.get("role", "")
    content = d.get("content", "")
    
    if role == "assistant":
        tool_calls = None
        if d.get("tool_calls"):
            tool_calls = [
                AssistantPromptMessage.ToolCall(
                    id=tc["id"],
                    type="function",
                    function=AssistantPromptMessage.ToolCall.ToolCallFunction(
                        name=tc["name"],
                        arguments=json.dumps(tc["arguments"], ensure_ascii=False)
                        if isinstance(tc["arguments"], dict)
                        else tc["arguments"],
                    ),
                )
                for tc in d["tool_calls"]
            ]
        return AssistantPromptMessage(
            content=content,
            tool_calls=tool_calls or [],
        )
    
    elif role == "tool":
        return ToolPromptMessage(
            content=content,
            tool_call_id=d.get("tool_call_id", ""),
            name=d.get("name", ""),
        )
    
    elif role == "user":
        return UserPromptMessage(content=content)
    
    else:
        # Fallback
        return UserPromptMessage(content=content)


def prompt_messages_to_turn(
    user_query: str,
    messages: list[PromptMessage],
    iteration_count: int = 1,
    usage: dict[str, Any] | None = None,
) -> Turn:
    """Convert a list of PromptMessages to a Turn.
    
    Args:
        user_query: The user's input query for this turn
        messages: List of assistant and tool messages from ReAct loop
        iteration_count: Number of ReAct iterations
        usage: Token usage stats
        
    Returns:
        Turn object ready for storage
    """
    turn_messages: list[TurnMessage] = []
    
    for msg in messages:
        d = prompt_message_to_dict(msg)
        # Skip user messages - we store user_query separately
        if d["role"] == "user":
            continue
        turn_messages.append(TurnMessage.from_dict(d))
    
    return Turn.create(
        user_query=user_query,
        messages=turn_messages,
        iteration_count=iteration_count,
        usage=usage,
    )


def turn_to_prompt_messages(
    turn: Turn,
    include_user: bool = True,
    max_chars: int | None = None,
) -> list[PromptMessage]:
    """Convert a Turn back to list of PromptMessages.
    
    Args:
        turn: Turn to convert
        include_user: Whether to include UserPromptMessage at the start
        max_chars: Optional max characters per message content (truncation)
        
    Returns:
        List of PromptMessages ready for LLM context
    """
    result: list[PromptMessage] = []
    
    # Add user message first
    if include_user and turn.user_query:
        content = turn.user_query
        if max_chars and len(content) > max_chars:
            content = content[:max_chars] + "... [truncated]"
        result.append(UserPromptMessage(content=content))
    
    # Add assistant and tool messages
    for msg in turn.messages:
        d = msg.to_dict()
        
        # Truncate content if needed
        if max_chars and len(d.get("content", "")) > max_chars:
            d["content"] = d["content"][:max_chars] + "... [truncated]"
        
        result.append(dict_to_prompt_message(d))
    
    return result


def _extract_content(content: Any) -> str:
    """Extract string content from various content types."""
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        # Handle list of content blocks
        parts = []
        for item in content:
            if hasattr(item, "data"):
                parts.append(str(item.data))
            elif isinstance(item, dict) and "data" in item:
                parts.append(str(item["data"]))
            else:
                parts.append(str(item))
        return "\n".join(parts)
    return str(content)


def _parse_arguments(args: str | dict) -> dict[str, Any]:
    """Parse tool call arguments."""
    if isinstance(args, dict):
        return args
    if isinstance(args, str):
        try:
            return json.loads(args)
        except json.JSONDecodeError:
            return {"raw": args}
    return {}
