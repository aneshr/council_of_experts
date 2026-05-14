"""
Tests for the router chat graph: pure node logic and nodes with mocked LLM/chain.

- fallback_node, route_after_router: no mocks.
- router_node, stream_expert_node: patch utils.helper (initialize_llm, router_expert, llm_response, chat_expert).
"""

import pytest
from unittest.mock import MagicMock, patch

from app.graph.router_chat import (
    RouterChatState,
    fallback_node,
    route_after_router,
    router_node,
    stream_expert_node,
)


class TestRouteAfterRouter:
    """Pure logic: next node name from state."""

    def test_none_expert_returns_fallback(self):
        state: RouterChatState = {"chosen_expert": "None", "question": "x", "expert_list": []}
        assert route_after_router(state) == "fallback"

    def test_chosen_expert_returns_stream_expert(self):
        state: RouterChatState = {"chosen_expert": "science", "question": "x", "expert_list": []}
        assert route_after_router(state) == "stream_expert"

    def test_missing_chosen_expert_returns_stream_expert(self):
        state: RouterChatState = {"question": "x", "expert_list": []}
        assert route_after_router(state) == "stream_expert"


class TestFallbackNode:
    """fallback_node returns fixed answer_chunks."""

    def test_returns_clarification_message(self):
        state: RouterChatState = {"question": "?", "expert_list": [], "chosen_expert": "None"}
        out = fallback_node(state)
        assert "answer_chunks" in out
        assert len(out["answer_chunks"]) == 1
        assert "rephrase" in out["answer_chunks"][0].lower()


class TestRouterNode:
    """router_node with mocked LLM/chain."""

    @patch("app.graph.router_chat.llm_response")
    @patch("app.graph.router_chat.router_expert")
    @patch("app.graph.router_chat.initialize_llm")
    def test_chooses_expert_from_chain(
        self, mock_init_llm, mock_router_expert, mock_llm_response
    ):
        mock_llm = MagicMock()
        mock_init_llm.return_value = mock_llm
        mock_chain = MagicMock()
        mock_router_expert.return_value = mock_chain
        mock_llm_response.return_value = "science"

        state: RouterChatState = {
            "question": "What is gravity?",
            "expert_list": ["science", "math", "None"],
        }
        out = router_node(state)

        assert out["chosen_expert"] == "science"
        assert out["router_raw_output"] == "science"
        mock_router_expert.assert_called_once_with(
            llm=mock_llm, expert_list=["science", "math", "None"], question="What is gravity?"
        )
        mock_llm_response.assert_called_once()

    @patch("app.graph.router_chat.llm_response")
    @patch("app.graph.router_chat.router_expert")
    @patch("app.graph.router_chat.initialize_llm")
    def test_invalid_expert_maps_to_none(
        self, mock_init_llm, mock_router_expert, mock_llm_response
    ):
        mock_init_llm.return_value = MagicMock()
        mock_router_expert.return_value = MagicMock()
        mock_llm_response.return_value = "unknown_expert"

        state: RouterChatState = {
            "question": "?",
            "expert_list": ["science", "math", "None"],
        }
        out = router_node(state)

        assert out["chosen_expert"] == "None"


class TestStreamExpertNode:
    """stream_expert_node with mocked LLM/chain."""

    @patch("app.graph.router_chat.format_chat_history")
    @patch("app.graph.router_chat.chat_expert")
    @patch("app.graph.router_chat.initialize_llm")
    def test_returns_answer_chunks_from_invoke(
        self, mock_init_llm, mock_chat_expert, mock_format_chat_history
    ):
        mock_llm = MagicMock()
        mock_init_llm.return_value = mock_llm
        mock_chain = MagicMock()
        mock_chain.invoke.return_value = MagicMock(content="The answer is 42.")
        mock_chat_expert.return_value = mock_chain
        mock_format_chat_history.return_value = ""

        state: RouterChatState = {
            "chosen_expert": "science",
            "question": "What is 6*7?",
            "history": [],
        }
        config = MagicMock()
        out = stream_expert_node(state, config)

        assert out["answer_chunks"] == ["The answer is 42."]
        mock_chat_expert.assert_called_once_with(
            mock_llm, "science", "What is 6*7?", []
        )
        mock_chain.invoke.assert_called_once()

    @patch("app.graph.router_chat.format_chat_history")
    @patch("app.graph.router_chat.chat_expert")
    @patch("app.graph.router_chat.initialize_llm")
    def test_on_exception_returns_error_chunk(
        self, mock_init_llm, mock_chat_expert, mock_format_chat_history
    ):
        mock_init_llm.return_value = MagicMock()
        mock_chain = MagicMock()
        mock_chain.invoke.side_effect = RuntimeError("LLM failed")
        mock_chat_expert.return_value = mock_chain
        mock_format_chat_history.return_value = ""

        state: RouterChatState = {
            "chosen_expert": "math",
            "question": "?",
            "history": [],
        }
        config = MagicMock()
        out = stream_expert_node(state, config)

        assert "error" in out
        assert "Sorry, an error occurred" in out["answer_chunks"][0]
