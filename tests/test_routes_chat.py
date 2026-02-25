"""
Tests for chat routes using FastAPI TestClient.

GET /api/v1/ask/ and POST /api/v1/ask/stream with router_chat_app.stream mocked
so no real LangGraph/Ollama is required.
"""

import json
from unittest.mock import patch, MagicMock

import pytest


def _mock_stream_updates_then_messages(chosen_expert: str, content: str):
    """Yield (mode, chunk) events in the shape the route expects."""
    yield ("updates", {"router": {"chosen_expert": chosen_expert}})
    msg = MagicMock()
    msg.content = content
    yield ("messages", (msg, {}))


class TestAskRoot:
    """GET /api/v1/ask/."""

    def test_get_returns_200_and_message(self, client):
        response = client.get("/api/v1/ask/")
        assert response.status_code == 200
        data = response.json()
        assert "message" in data


class TestStreamChat:
    """POST /api/v1/ask/stream with mocked graph stream."""

    @patch("app.routes.chat.router_chat_app")
    def test_stream_returns_200_and_json_lines(self, mock_router_app, client, sample_chat_request):
        mock_router_app.stream.return_value = _mock_stream_updates_then_messages(
            chosen_expert="science",
            content="Gravity is a force that attracts objects with mass.",
        )

        response = client.post("/api/v1/ask/stream", json=sample_chat_request)

        assert response.status_code == 200
        text = response.text
        lines = [line for line in text.strip().split("\n") if line]
        assert len(lines) >= 2
        # First line(s) may be content; last should be event "end"
        parsed = [json.loads(line) for line in lines]
        experts = [p.get("expert") for p in parsed]
        assert "science" in experts
        assert any(p.get("event") == "end" for p in parsed)
        assert any("Gravity" in (p.get("content") or "") for p in parsed)

    @patch("app.routes.chat.router_chat_app")
    def test_stream_fallback_path_returns_router_content(self, mock_router_app, client):
        """When graph yields fallback node, response has expert Router and answer_chunks."""
        def fallback_stream(*args, **kwargs):
            yield ("updates", {"fallback": {"answer_chunks": ["Please rephrase your question."]}})

        mock_router_app.stream.return_value = fallback_stream()

        response = client.post(
            "/api/v1/ask/stream",
            json={"question": "??", "history": [], "experts": ["science"]},
        )

        assert response.status_code == 200
        lines = [line for line in response.text.strip().split("\n") if line]
        parsed = [json.loads(line) for line in lines]
        assert any(p.get("expert") == "Router" for p in parsed)
        assert any("rephrase" in (p.get("content") or "").lower() for p in parsed)
        assert any(p.get("event") == "end" for p in parsed)

    def test_stream_missing_question_returns_422(self, client, sample_chat_request):
        sample_chat_request.pop("question", None)
        response = client.post("/api/v1/ask/stream", json=sample_chat_request)
        assert response.status_code == 422


class TestVoiceQuery:
    """POST /api/v1/ask/voice-query with mocked Whisper and graph stream."""

    @patch("app.routes.chat.router_chat_app")
    @patch("app.routes.chat.initialize_whisper")
    @patch("app.routes.chat.convert_to_wav")
    def test_voice_query_returns_transcript_and_stream(
        self, mock_convert_to_wav, mock_init_whisper, mock_router_app, client
    ):
        mock_convert_to_wav.return_value = "/tmp/fake.wav"
        mock_whisper = MagicMock()
        mock_whisper.transcribe.return_value = {"text": "What is gravity?"}
        mock_init_whisper.return_value = mock_whisper
        mock_router_app.stream.return_value = _mock_stream_updates_then_messages(
            chosen_expert="science",
            content="Gravity is a force.",
        )

        meta = json.dumps({
            "history": [],
            "experts": ["science"],
        })
        response = client.post(
            "/api/v1/ask/voice-query",
            files={"audio": ("query.webm", b"fake-audio-bytes", "audio/webm")},
            data={"meta": meta},
        )

        assert response.status_code == 200
        lines = [line for line in response.text.strip().split("\n") if line]
        parsed = [json.loads(line) for line in lines]
        transcript = next((p for p in parsed if p.get("event") == "transcript"), None)
        assert transcript is not None
        assert transcript.get("content") == "What is gravity?"
        assert any(p.get("event") == "end" for p in parsed)

    def test_voice_query_invalid_meta_returns_400(self, client):
        response = client.post(
            "/api/v1/ask/voice-query",
            files={"audio": ("q.webm", b"x", "audio/webm")},
            data={"meta": "not valid json"},
        )
        assert response.status_code == 400


class TestByod:
    """POST /api/v1/ask/byod with mocked ingest_document."""

    @patch("app.routes.chat.ingest_document")
    def test_byod_returns_ingest_summary(self, mock_ingest, client):
        mock_ingest.return_value = {
            "doc_id": "test-uuid",
            "doc_name": "test.txt",
            "filename": "test.txt",
            "file_type": "txt",
            "num_chunks": 3,
            "tags": [],
            "ingested_at": "2026-01-01T00:00:00Z",
        }

        response = client.post(
            "/api/v1/ask/byod",
            files={"file": ("test.txt", b"Hello world.\n\nSome content.", "text/plain")},
            data={"doc_name": "test.txt", "source": "upload", "language": "en"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["doc_id"] == "test-uuid"
        assert data["doc_name"] == "test.txt"
        assert data["num_chunks"] == 3
        assert data["file_type"] == "txt"

    @patch("app.routes.chat.ingest_document")
    def test_byod_empty_file_returns_400(self, mock_ingest, client):
        response = client.post(
            "/api/v1/ask/byod",
            files={"file": ("empty.txt", b"", "text/plain")},
            data={"source": "upload"},
        )
        assert response.status_code == 400
        mock_ingest.assert_not_called()
