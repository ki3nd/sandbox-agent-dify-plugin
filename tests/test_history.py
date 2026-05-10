"""Tests for history storage."""

import json
import pytest
from history.models import TurnMessage, Turn, HistoryData
from history.converter import (
    prompt_message_to_dict,
    dict_to_prompt_message,
    prompt_messages_to_turn,
    turn_to_prompt_messages,
)


class TestTurnMessage:
    """Tests for TurnMessage."""
    
    def test_assistant_message_to_dict(self):
        msg = TurnMessage(
            role="assistant",
            content="Hello",
            tool_calls=[{"id": "1", "name": "exec_command", "arguments": {"cmd": "ls"}}],
        )
        d = msg.to_dict()
        assert d["role"] == "assistant"
        assert d["content"] == "Hello"
        assert d["tool_calls"][0]["name"] == "exec_command"
    
    def test_tool_message_to_dict(self):
        msg = TurnMessage(
            role="tool",
            content="output",
            tool_call_id="1",
            name="exec_command",
        )
        d = msg.to_dict()
        assert d["role"] == "tool"
        assert d["tool_call_id"] == "1"
        assert d["name"] == "exec_command"
    
    def test_from_dict(self):
        d = {
            "role": "assistant",
            "content": "test",
            "tool_calls": [{"id": "1", "name": "test", "arguments": {}}],
        }
        msg = TurnMessage.from_dict(d)
        assert msg.role == "assistant"
        assert msg.content == "test"
        assert msg.tool_calls[0]["name"] == "test"


class TestTurn:
    """Tests for Turn."""
    
    def test_create(self):
        turn = Turn.create(
            user_query="hello",
            messages=[TurnMessage(role="assistant", content="hi")],
            iteration_count=1,
        )
        assert turn.user_query == "hello"
        assert len(turn.messages) == 1
        assert turn.turn_id  # UUID generated
        assert turn.timestamp > 0
    
    def test_to_dict_and_back(self):
        turn = Turn.create(
            user_query="test query",
            messages=[
                TurnMessage(role="assistant", content="thinking", tool_calls=[{"id": "1", "name": "exec", "arguments": {}}]),
                TurnMessage(role="tool", content="result", tool_call_id="1", name="exec"),
            ],
            iteration_count=2,
            usage={"total_tokens": 100},
        )
        d = turn.to_dict()
        restored = Turn.from_dict(d)
        
        assert restored.turn_id == turn.turn_id
        assert restored.user_query == turn.user_query
        assert len(restored.messages) == 2
        assert restored.usage["total_tokens"] == 100


class TestHistoryData:
    """Tests for HistoryData."""
    
    def test_empty(self):
        history = HistoryData()
        assert history.version == 1
        assert len(history.turns) == 0
        assert history.is_empty() if hasattr(history, 'is_empty') else len(history.turns) == 0
    
    def test_add_turn(self):
        history = HistoryData()
        turn = Turn.create(user_query="test", messages=[])
        history.add_turn(turn)
        assert len(history.turns) == 1
    
    def test_to_json_and_back(self):
        history = HistoryData()
        history.add_turn(Turn.create(user_query="q1", messages=[]))
        history.add_turn(Turn.create(user_query="q2", messages=[]))
        
        json_str = history.to_json()
        restored = HistoryData.from_json(json_str)
        
        assert len(restored.turns) == 2
        assert restored.turns[0].user_query == "q1"
        assert restored.turns[1].user_query == "q2"
    
    def test_from_empty_json(self):
        history = HistoryData.from_json("")
        assert len(history.turns) == 0
    
    def test_from_invalid_json(self):
        history = HistoryData.from_json("not valid json")
        assert len(history.turns) == 0
    
    def test_get_recent_turns(self):
        history = HistoryData()
        for i in range(5):
            history.add_turn(Turn.create(user_query=f"q{i}", messages=[]))
        
        recent = history.get_recent_turns(3)
        assert len(recent) == 3
        assert recent[0].user_query == "q2"
        assert recent[2].user_query == "q4"
    
    def test_evict_oldest(self):
        history = HistoryData()
        # Add turns until we exceed a small limit
        for i in range(10):
            history.add_turn(Turn.create(
                user_query=f"query {i}" * 100,  # Make it bigger
                messages=[TurnMessage(role="assistant", content="x" * 500)],
            ))
        
        initial_size = history.size_bytes()
        evicted = history.evict_oldest(initial_size // 2)
        
        assert evicted > 0
        assert history.size_bytes() <= initial_size // 2


class TestConverter:
    """Tests for converter functions."""
    
    def test_prompt_messages_to_turn(self):
        # This test requires dify_plugin, skip if not available
        try:
            from dify_plugin.entities.model.message import (
                AssistantPromptMessage,
                ToolPromptMessage,
            )
        except ImportError:
            pytest.skip("dify_plugin not available")
        
        messages = [
            AssistantPromptMessage(
                content="Let me run a command",
                tool_calls=[
                    AssistantPromptMessage.ToolCall(
                        id="call_1",
                        type="function",
                        function=AssistantPromptMessage.ToolCall.ToolCallFunction(
                            name="exec_command",
                            arguments='{"command": "ls"}',
                        ),
                    )
                ],
            ),
            ToolPromptMessage(
                content="file1.txt\nfile2.txt",
                tool_call_id="call_1",
                name="exec_command",
            ),
            AssistantPromptMessage(
                content="I found 2 files.",
                tool_calls=[],
            ),
        ]
        
        turn = prompt_messages_to_turn(
            user_query="list files",
            messages=messages,
            iteration_count=2,
        )
        
        assert turn.user_query == "list files"
        assert len(turn.messages) == 3
        assert turn.messages[0].role == "assistant"
        assert turn.messages[0].tool_calls[0]["name"] == "exec_command"
        assert turn.messages[1].role == "tool"
        assert turn.messages[2].content == "I found 2 files."
