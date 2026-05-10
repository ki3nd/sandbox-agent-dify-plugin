"""History manager for persisting conversation turns."""

from typing import Any, Protocol

from dify_plugin.entities.model.message import PromptMessage

from history.models import HistoryData, Turn
from history.converter import prompt_messages_to_turn, turn_to_prompt_messages


# Storage limits
MAX_HISTORY_BYTES = 900_000  # 900KB, reserve 100KB for other keys
MAX_HISTORY_TURNS = 100  # Hard cap on turn count


class StorageProtocol(Protocol):
    """Protocol for Dify session.storage interface."""
    
    def get(self, key: str) -> bytes: ...
    def set(self, key: str, value: bytes) -> None: ...
    def delete(self, key: str) -> None: ...


class HistoryManager:
    """Manages conversation history in session.storage.
    
    Persists turns as JSON, handles size limits and eviction.
    """
    
    STORAGE_KEY_PREFIX = "sandbox_agent:history:"
    
    def __init__(
        self,
        storage: StorageProtocol,
        session_id: str = "global",
        max_bytes: int = MAX_HISTORY_BYTES,
        max_turns: int = MAX_HISTORY_TURNS,
    ):
        """Initialize history manager.
        
        Args:
            storage: Dify session.storage or compatible interface
            session_id: Session identifier (from conversation_id, chat_id, etc.)
            max_bytes: Maximum storage size in bytes
            max_turns: Maximum number of turns to keep
        """
        self.storage = storage
        self.session_id = session_id
        self.max_bytes = max_bytes
        self.max_turns = max_turns
        self._storage_key = f"{self.STORAGE_KEY_PREFIX}{session_id}"
        self._history: HistoryData | None = None
    
    def load(self) -> HistoryData:
        """Load history from storage.
        
        Returns:
            HistoryData (empty if not found or invalid)
        """
        if self._history is not None:
            return self._history
        
        try:
            data = self.storage.get(self._storage_key)
            if data:
                json_str = data.decode("utf-8")
                self._history = HistoryData.from_json(json_str)
            else:
                self._history = HistoryData()
        except Exception:
            self._history = HistoryData()
        
        return self._history
    
    def save(self) -> None:
        """Save history to storage.
        
        Handles eviction if size exceeds limits.
        """
        if self._history is None:
            return
        
        # Enforce max turns
        while len(self._history.turns) > self.max_turns:
            self._history.turns.pop(0)
        
        # Enforce max bytes
        self._history.evict_oldest(self.max_bytes)
        
        # Save
        json_str = self._history.to_json()
        self.storage.set(self._storage_key, json_str.encode("utf-8"))
    
    def to_prompt_messages(
        self,
        memory_turns: int = 10,
        max_chars_per_turn: int = 4000,
    ) -> list[PromptMessage]:
        """Get recent turns as PromptMessages for LLM context.
        
        Args:
            memory_turns: Number of recent turns to include
            max_chars_per_turn: Max characters per message (truncation)
            
        Returns:
            Flat list of PromptMessages (user + assistant + tool)
        """
        history = self.load()
        recent_turns = history.get_recent_turns(memory_turns)
        
        result: list[PromptMessage] = []
        for turn in recent_turns:
            messages = turn_to_prompt_messages(
                turn,
                include_user=True,
                max_chars=max_chars_per_turn,
            )
            result.extend(messages)
        
        return result
    
    def save_turn(
        self,
        user_query: str,
        messages: list[PromptMessage],
        iteration_count: int = 1,
        usage: dict[str, Any] | None = None,
    ) -> Turn:
        """Save a complete turn to history.
        
        Args:
            user_query: The user's input query
            messages: All assistant + tool messages from ReAct loop
            iteration_count: Number of ReAct iterations
            usage: Token usage stats
            
        Returns:
            The saved Turn object
        """
        history = self.load()
        
        turn = prompt_messages_to_turn(
            user_query=user_query,
            messages=messages,
            iteration_count=iteration_count,
            usage=usage,
        )
        
        history.add_turn(turn)
        self.save()
        
        return turn
    
    def clear(self) -> None:
        """Clear all history."""
        self._history = HistoryData()
        try:
            self.storage.delete(self._storage_key)
        except Exception:
            pass
    
    def get_turn_count(self) -> int:
        """Get number of stored turns."""
        return len(self.load().turns)
