"""
Shared pytest fixtures for the chat app tests.

Provides FastAPI TestClient and sample request/history payloads.

Optional deps (whisper, pydub) are mocked at import so the app loads without them.
"""

import sys
from unittest.mock import MagicMock

# Allow app to load when optional voice deps are not installed
if "whisper" not in sys.modules:
    sys.modules["whisper"] = MagicMock()
if "pydub" not in sys.modules:
    _pydub = MagicMock()
    _pydub.AudioSegment = MagicMock()
    sys.modules["pydub"] = _pydub

import pytest
from fastapi.testclient import TestClient

from models.chat_models import ChatRequest, Message


@pytest.fixture
def client() -> TestClient:
    """FastAPI TestClient for the main app (imports app on first use)."""
    from app.main import app
    return TestClient(app)


@pytest.fixture
def sample_history() -> list:
    """Sample chat history (list of dicts with role/content)."""
    return [
        {"role": "user", "content": "What is photosynthesis?"},
        {"role": "assistant", "content": "Photosynthesis is the process by which plants use sunlight to make food."},
    ]


@pytest.fixture
def sample_chat_request(sample_history: list) -> dict:
    """Sample POST body for /api/v1/ask/stream."""
    return {
        "question": "Tell me more.",
        "history": sample_history,
        "experts": ["science", "math"],
    }


@pytest.fixture
def sample_chat_request_model(sample_chat_request: dict) -> ChatRequest:
    """ChatRequest model instance from sample payload."""
    return ChatRequest(**sample_chat_request)
