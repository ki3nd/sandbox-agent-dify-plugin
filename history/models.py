"""Data models for history storage."""

import json
import uuid
import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class TurnMessage:
    """A single message in a turn.
    
    Represents assistant or tool messages in JSON-serializable format.
    """
    role: str  # "assistant" or "tool"
    content: str
    
    # For assistant messages with tool calls
    tool_calls: list[dict[str, Any]] | None = None
    
    # For tool messages
    tool_call_id: str | None = None
    name: str | None = None  # Tool name
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict."""
        d: dict[str, Any] = {
            "role": self.role,
            "content": self.content,
        }
        if self.tool_calls:
            d["tool_calls"] = self.tool_calls
        if self.tool_call_id:
            d["tool_call_id"] = self.tool_call_id
        if self.name:
            d["name"] = self.name
        return d
    
    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "TurnMessage":
        """Create from dict."""
        return cls(
            role=d["role"],
            content=d.get("content", ""),
            tool_calls=d.get("tool_calls"),
            tool_call_id=d.get("tool_call_id"),
            name=d.get("name"),
        )


@dataclass
class Turn:
    """A complete conversation turn.
    
    One turn = one _invoke() lifecycle:
    - User query
    - All ReAct iterations (assistant + tool messages)
    - Final answer
    """
    turn_id: str
    timestamp: int  # Unix seconds
    user_query: str  # The user's input query
    messages: list[TurnMessage]  # All assistant + tool messages
    iteration_count: int = 1  # Number of ReAct iterations
    usage: dict[str, Any] | None = None  # Token usage stats
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict."""
        d: dict[str, Any] = {
            "turn_id": self.turn_id,
            "timestamp": self.timestamp,
            "user_query": self.user_query,
            "messages": [m.to_dict() for m in self.messages],
            "iteration_count": self.iteration_count,
        }
        if self.usage:
            d["usage"] = self.usage
        return d
    
    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Turn":
        """Create from dict."""
        return cls(
            turn_id=d["turn_id"],
            timestamp=d["timestamp"],
            user_query=d.get("user_query", ""),
            messages=[TurnMessage.from_dict(m) for m in d.get("messages", [])],
            iteration_count=d.get("iteration_count", 1),
            usage=d.get("usage"),
        )
    
    @classmethod
    def create(
        cls,
        user_query: str,
        messages: list[TurnMessage],
        iteration_count: int = 1,
        usage: dict[str, Any] | None = None,
    ) -> "Turn":
        """Create a new turn with auto-generated ID and timestamp."""
        return cls(
            turn_id=str(uuid.uuid4()),
            timestamp=int(time.time()),
            user_query=user_query,
            messages=messages,
            iteration_count=iteration_count,
            usage=usage,
        )


@dataclass
class HistoryData:
    """Complete history data structure.
    
    Stored as JSON in session.storage.
    """
    version: int = 1
    turns: list[Turn] = field(default_factory=list)
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            "version": self.version,
            "turns": [t.to_dict() for t in self.turns],
        }
    
    def to_json(self) -> str:
        """Serialize to JSON string."""
        return json.dumps(self.to_dict(), ensure_ascii=False)
    
    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "HistoryData":
        """Create from dict."""
        return cls(
            version=d.get("version", 1),
            turns=[Turn.from_dict(t) for t in d.get("turns", [])],
        )
    
    @classmethod
    def from_json(cls, json_str: str) -> "HistoryData":
        """Deserialize from JSON string."""
        if not json_str or json_str.strip() == "":
            return cls()
        try:
            d = json.loads(json_str)
            return cls.from_dict(d)
        except json.JSONDecodeError:
            return cls()
    
    def add_turn(self, turn: Turn) -> None:
        """Add a turn to history."""
        self.turns.append(turn)
    
    def get_recent_turns(self, n: int) -> list[Turn]:
        """Get the most recent n turns."""
        if n <= 0:
            return []
        return self.turns[-n:]
    
    def size_bytes(self) -> int:
        """Get approximate size in bytes."""
        return len(self.to_json().encode("utf-8"))
    
    def evict_oldest(self, max_bytes: int) -> int:
        """Evict oldest turns until size is under max_bytes.
        
        Returns:
            Number of turns evicted.
        """
        evicted = 0
        while self.turns and self.size_bytes() > max_bytes:
            self.turns.pop(0)
            evicted += 1
        return evicted
