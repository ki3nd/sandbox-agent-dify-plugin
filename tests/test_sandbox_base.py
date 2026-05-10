"""Tests for sandbox base classes."""

import pytest
from sandbox.base import CommandResult


class TestCommandResult:
    """Tests for CommandResult dataclass."""

    def test_ok_with_zero_exit_code(self):
        result = CommandResult(stdout="hello", stderr="", exit_code=0)
        assert result.ok() is True

    def test_ok_with_nonzero_exit_code(self):
        result = CommandResult(stdout="", stderr="error", exit_code=1)
        assert result.ok() is False

    def test_format_basic(self):
        result = CommandResult(stdout="hello world", stderr="", exit_code=0)
        formatted = result.format()
        assert "<stdout>" in formatted
        assert "hello world" in formatted
        assert "<exit_code>0</exit_code>" in formatted

    def test_format_with_stderr(self):
        result = CommandResult(stdout="out", stderr="err", exit_code=1)
        formatted = result.format()
        assert "<stdout>" in formatted
        assert "<stderr>" in formatted
        assert "err" in formatted
        assert "<exit_code>1</exit_code>" in formatted

    def test_format_truncation(self):
        long_output = "x" * 1000
        result = CommandResult(stdout=long_output, stderr="", exit_code=0)
        formatted = result.format(max_chars=100)
        assert result.truncated is True
        assert "[truncated]" in formatted
        # Check formatted output is truncated, not original stdout
        assert len(formatted) <= 200  # Reasonable limit for formatted output

    def test_format_with_timeout(self):
        result = CommandResult(stdout="", stderr="timeout", exit_code=124, timed_out=True)
        formatted = result.format()
        assert "[Command timed out]" in formatted

    def test_format_no_truncation_when_under_limit(self):
        result = CommandResult(stdout="short", stderr="", exit_code=0)
        formatted = result.format(max_chars=1000)
        assert result.truncated is False
        assert "[truncated]" not in formatted
