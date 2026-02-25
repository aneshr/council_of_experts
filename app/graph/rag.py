"""
LangGraph graph for BYOD RAG chat (/ask/byod-chat).

This graph focuses on the **answer generation** step:
- It assumes that document retrieval has already been done in the route.
- The route passes question, history, and a pre-built context string.
- The graph runs a RAG-style LLM chain and can be streamed with
  `stream_mode=["messages"]` so tokens are emitted incrementally.
"""

from typing import TypedDict, List, Any, Optional

from langchain_core.runnables import RunnableConfig
from langgraph.graph import StateGraph, END

from langchain_core.prompts.prompt import PromptTemplate

from utils.helper import initialize_llm, format_chat_history


class RagChatState(TypedDict, total=False):
    """
    State passed through the RAG chat graph.

    Fields
    ------
    question : str
        Current user question.
    history : list[Any]
        Prior conversation messages; converted to a readable history string.
    context : str
        Pre-built document context string (citations + text).
    answer_chunks : list[str]
        Collected answer chunks (non-streaming fallback).
    events : list[dict]
        Optional event log for debugging/telemetry.
    error : str | None
        Error message if answer generation fails.
    """

    question: str
    history: List[Any]
    context: str
    answer_chunks: List[str]
    events: List[dict]
    error: Optional[str]


def rag_answer_node(state: RagChatState, config: RunnableConfig) -> RagChatState:
    """
    Run a RAG-style prompt over the provided document context.

    This node:
    - Uses the same prompt structure previously coded in the /byod-chat route.
    - Relies on LangGraph + LCEL to enable token streaming when the graph
      is driven with `stream_mode=["messages"]` and this node is passed `config`.
    """
    question = state["question"]
    history = state.get("history") or []
    context = state.get("context") or ""

    llm = initialize_llm()

    promptT = PromptTemplate(
        input_variables=["chat_history", "question", "context"],
        template=(
            "You are a helpful assistant answering questions based on the provided documents.\n"
            "Use the document context as your PRIMARY source of truth.\n"
            "If the answer is not clearly supported by the documents, say you don't know.\n\n"
            "Document context:\n"
            "{context}\n\n"
            "Conversation so far:\n"
            "{chat_history}\n\n"
            "User: {question}\n"
            "Assistant:"
        ),
    )

    chain = promptT | llm
    chat_history_str = format_chat_history(history)

    try:
        # Pass `config` so that LangGraph can stream LLM tokens in "messages" mode.
        result = chain.invoke(
            {
                "chat_history": chat_history_str,
                "question": question,
                "context": context,
            },
            config=config,
        )
        content = getattr(result, "content", None)
        if content is None:
            content = str(result)
        return {"answer_chunks": [content]}
    except Exception as e:
        return {
            "error": str(e),
            "answer_chunks": [
                "Sorry, an error occurred while generating the RAG response."
            ],
        }


graph = StateGraph(RagChatState)
graph.add_node("rag_answer", rag_answer_node)
graph.set_entry_point("rag_answer")
graph.add_edge("rag_answer", END)

rag_chat_app = graph.compile()

__all__ = [
    "RagChatState",
    "rag_answer_node",
    "rag_chat_app",
]

