"""
Router chat graph for /ask/stream: state and node functions.

Use with LangGraph: define a StateGraph(RouterChatState), add these nodes,
add conditional edges from validate_expert_node, then compile.
"""

import json
from typing import TypedDict, List, Optional, Any

from langchain_core.runnables import RunnableConfig


class RouterChatState(TypedDict, total=False):
    """State passed through the router chat graph."""

    question: str
    history: List[Any]  # list of Message-like dicts: {"role": str, "content": str}
    expert_list: List[str]
    chosen_expert: Optional[str]
    router_raw_output: Optional[str]
    answer_chunks: List[str]  # chunks from expert (or fallback); route streams these
    events: List[dict]
    error: Optional[str]


def router_node(state: RouterChatState) -> RouterChatState:
    """
    Choose which expert should handle the question using the existing router chain.
    Returns partial state: router_raw_output, chosen_expert, and one event.
    """
    from utils.helper import initialize_llm, router_expert, llm_response

    question = state["question"]
    expert_list = state["expert_list"]

    llm = initialize_llm()
    chain = router_expert(llm=llm, expert_list=expert_list, question=question)
    raw = llm_response(chain, question=question)

    chosen = (raw or "").strip().split("\n")[0].strip()
    if chosen not in expert_list:
        chosen = "None"

    events = list(state.get("events") or [])
    events.append(
        {"type": "router_choice", "expert": chosen, "raw_preview": (raw or "")[:100]}
    )
    return {
        "router_raw_output": raw,
        "chosen_expert": chosen,
        "events": events,
    }


def fallback_node(state: RouterChatState) -> RouterChatState:
    """
    When no expert was chosen, set a single clarification message as the answer.
    Returns partial state: answer_chunks.
    """
    return {
        "answer_chunks": [
            "I am not sure about the question. Please rephrase the question."
        ],
    }

def route_after_router(state: RouterChatState) -> str:
    """
    Return the name of the next node after the router. Used in add_conditional_edges.
    """
    if state.get("chosen_expert") == "None":
        return "fallback"
    return "stream_expert"


def stream_expert_node(state: RouterChatState, config: RunnableConfig) -> RouterChatState:
    """
    Run the chosen expert chain inside the graph. Pass config to invoke() so that
    when the graph is streamed with stream_mode="messages", LangGraph can stream
    LLM tokens from this node to the client.
    """
    from utils.helper import initialize_llm, chat_expert, format_chat_history

    chosen = state["chosen_expert"]
    question = state["question"]
    history = state.get("history") or []

    llm = initialize_llm()
    chain = chat_expert(llm, chosen, question, history)
    chat_history_str = format_chat_history(history)
    try:
        result = chain.invoke(
            {"chat_history": chat_history_str, "question": question},
            config=config,
        )
        content = result.content if hasattr(result, "content") else str(result)
        return {"answer_chunks": [content]}
    except Exception as e:
        return {"error": str(e), "answer_chunks": ["Sorry, an error occurred while generating the response."]}
