"""
Tests for Pydantic chat models: Message and ChatRequest.

Covers valid payloads, defaults, and validation errors.
"""

import pytest
from pydantic import ValidationError

from models.chat_models import Message, ChatRequest


class TestMessage:
    """Message model validation."""

    def test_valid_message(self):
        msg = Message(role="user", content="Hello")
        assert msg.role == "user"
        assert msg.content == "Hello"

    def test_message_assistant(self):
        msg = Message(role="assistant", content="Hi there.")
        assert msg.role == "assistant"
        assert msg.content == "Hi there."

    def test_message_missing_role_raises(self):
        with pytest.raises(ValidationError):
            Message(content="Only content")

    def test_message_missing_content_raises(self):
        with pytest.raises(ValidationError):
            Message(role="user")


class TestChatRequest:
    """ChatRequest model validation and defaults."""

    def test_valid_minimal(self):
        req = ChatRequest(question="What is 2+2?")
        assert req.question == "What is 2+2?"
        assert req.history == []
        assert req.experts == ["science"]

    def test_valid_full(self):
        req = ChatRequest(
            question="Explain gravity",
            history=[Message(role="user", content="Hi"), Message(role="assistant", content="Hello")],
            experts=["science", "math"],
        )
        assert req.question == "Explain gravity"
        assert len(req.history) == 2
        assert req.history[0].content == "Hi"
        assert req.experts == ["science", "math"]

    def test_history_from_dicts(self):
        """History can be built from dicts (Pydantic coerces to Message)."""
        req = ChatRequest(
            question="Q",
            history=[{"role": "user", "content": "A"}, {"role": "assistant", "content": "B"}],
        )
        assert len(req.history) == 2
        assert req.history[0].role == "user"
        assert req.history[0].content == "A"

    def test_missing_question_raises(self):
        with pytest.raises(ValidationError):
            ChatRequest(history=[])

    def test_wrong_type_question_raises(self):
        with pytest.raises(ValidationError):
            ChatRequest(question=["not", "a", "string"])
