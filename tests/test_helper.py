"""
Unit tests for pure/simple helpers in utils.helper.

Focus on format_chat_history; other helpers that call LLM/Whisper can be covered later with mocks.
"""

import pytest

from utils.helper import format_chat_history
from models.chat_models import Message


class TestFormatChatHistory:
    """format_chat_history handles dicts, Pydantic Message, empty list, and skips empty content."""

    def test_empty_list(self):
        assert format_chat_history([]) == ""

    def test_list_of_dicts(self):
        history = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there."},
        ]
        result = format_chat_history(history)
        assert "User: Hello" in result
        assert "Assistant: Hi there." in result
        assert result == "User: Hello\nAssistant: Hi there."

    def test_list_of_messages(self):
        history = [
            Message(role="user", content="What is 2+2?"),
            Message(role="assistant", content="4"),
        ]
        result = format_chat_history(history)
        assert "User: What is 2+2?" in result
        assert "Assistant: 4" in result
        assert result == "User: What is 2+2?\nAssistant: 4"

    def test_system_role(self):
        history = [{"role": "system", "content": "You are helpful."}]
        result = format_chat_history(history)
        assert result == "System: You are helpful."

    def test_skips_empty_content(self):
        history = [
            {"role": "user", "content": "Hi"},
            {"role": "assistant", "content": ""},
            {"role": "user", "content": "Bye"},
        ]
        result = format_chat_history(history)
        assert "User: Hi" in result
        assert "User: Bye" in result
        assert "Assistant:" not in result or "Assistant: " in result
        assert result == "User: Hi\nUser: Bye"

    def test_mixed_dict_and_message(self):
        history = [
            {"role": "user", "content": "First"},
            Message(role="assistant", content="Second"),
        ]
        result = format_chat_history(history)
        assert "User: First" in result
        assert "Assistant: Second" in result
