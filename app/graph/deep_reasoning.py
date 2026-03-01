"""
LangGraph deep-reasoning chat: plan → solve → review → (loop or final answer).

The graph produces a structured plan, then an answer, then optionally
reviews and loops back to planning if the answer is inconsistent.
"""

from typing import TypedDict, List, Any, Optional

from langchain_core.runnables import RunnableConfig
from langchain_core.prompts.prompt import PromptTemplate
from langgraph.graph import StateGraph, END
from utils.helper import initialize_llm, format_chat_history

# Max times we allow looping back to plan after REVISION_NEEDED (prevents infinite loops)
MAX_REVISION_LOOPS = 2
# Max chars to keep per plan/answer in revision_attempts so the LLM sees the full earlier plan
MAX_REVISION_PLAN_CHARS = 3000
MAX_REVISION_ANSWER_CHARS = 3000


class DeepReasoningState(TypedDict, total=False):
    """
    State passed through the deep reasoning graph.

    Fields
    ------
    question : str
        Current user question.
    history : list
        Prior conversation messages; converted to a readable history string.
    plan : str
        Structured plan (steps, assumptions, checks) for downstream nodes.
    answer_chunks : list[str]
        Collected answer chunks (e.g. from solver or reviewer).
    review_needed : bool
        If True, conditional edge routes back to plan for another round.
    review_loop_count : int
        Number of times we have already looped plan → solver → reviewer (cap at MAX_REVISION_LOOPS).
    revision_attempts : list[dict]
        Prior plan/answer/verdict when we looped back after REVISION_NEEDED; passed into plan/solver for context.
    error : str | None
        Error message if a node fails.
    """

    question: str
    history: List[Any]
    plan: str  # structured plan (steps, assumptions, checks) for downstream nodes
    answer_chunks: List[str]
    review_needed: bool
    review_loop_count: int
    revision_attempts: List[dict]
    error: Optional[str]


def _format_revision_attempts(attempts: List[dict]) -> str:
    """Format revision_attempts for inclusion in prompts. Includes full stored plan and answer."""
    if not attempts:
        return "(This is the first attempt; no prior revisions.)"
    lines = []
    for i, a in enumerate(attempts, 1):
        plan_text = (a.get("plan") or "").strip()
        answer_text = (a.get("answer") or "").strip()
        verdict = (a.get("verdict") or "REVISION_NEEDED").strip()
        lines.append(
            f"Attempt {i}:\n"
            f"Plan:\n{plan_text}\n\n"
            f"Answer:\n{answer_text}\n\n"
            f"Verdict: {verdict}"
        )
    return "\n\n---\n\n".join(lines)


def plan_node(state: DeepReasoningState, config: RunnableConfig) -> DeepReasoningState:
    """
    Plan the steps to answer the question.
    Outputs a numbered list of steps, explicit assumptions, and required checks.
    Uses revision_attempts (if any) to avoid repeating prior failed approaches.
    """
    question = state["question"]
    history = state.get("history") or []
    revision_attempts = state.get("revision_attempts") or []
    revision_context = _format_revision_attempts(revision_attempts)

    llm = initialize_llm()

    promptT = PromptTemplate(
        input_variables=["chat_history", "question", "revision_context"],
        template=(
            "You are a helpful assistant. Based on the question, produce a clear plan.\n\n"
            "Previous revision attempt(s)—use to improve; do not repeat the same approach:\n{revision_context}\n\n"
            "For simple or personal questions (e.g. 'What is my name?', 'Do you know X?') where you may not have the information, use a very short plan: 1–2 steps. If the answer is that you don't have the information, say so briefly in the plan.\n\n"
            "For complex questions, output exactly three sections:\n"
            "1. **Steps**: A numbered list of steps to answer the question.\n"
            "2. **Assumptions**: Explicit assumptions about the question.\n"
            "3. **Required checks**: What to verify.\n\n"
            "User question: {question}\n\n"
            "Conversation so far: {chat_history}\n\n"
            "Assistant:"
        ),
    )
    chain = promptT | llm
    chat_history_str = format_chat_history(history)

    try:
        result = chain.invoke(
            {
                "chat_history": chat_history_str,
                "question": question,
                "revision_context": revision_context,
            },
            config=config,
        )
        content = result.content if hasattr(result, "content") else str(result)
        if content is None:
            content = str(result)
        return {"plan": content, "answer_chunks": [content]}
    except Exception as e:
        return {
            "error": str(e),
            "answer_chunks": ["Sorry, an error occurred while planning the steps."],
        }

def solver_node(state: DeepReasoningState, config: RunnableConfig) -> DeepReasoningState:
    """
    Solve the question using the plan (and prior revision attempts if any).
    """
    question = state["question"]
    plan = state["plan"]
    history = state.get("history") or []
    revision_context = _format_revision_attempts(state.get("revision_attempts") or [])

    llm = initialize_llm()

    promptT = PromptTemplate(
        input_variables=["chat_history", "question", "plan", "revision_context"],
        template=(
            "You are a helpful assistant. Based on the plan, question and conversation so far, answer the question directly.\n\n"
            "Prior attempt(s) that needed revision (do not repeat the same answer):\n{revision_context}\n\n"
            "Give a direct, conversational answer. Do not ask the user to 'proceed', 'let me know when you are ready', or 'let me know if you want to continue'. Do not output long meta-commentary.\n\n"
            "If you do not have the information (e.g. the user's name was never shared, or the question is about something not in the conversation), say so clearly in one or two sentences, e.g. 'I don't have access to your name in this chat—you haven't shared it yet.'\n\n"
            "Plan: {plan}\n\n"
            "Conversation so far: {chat_history}\n\n"
            "User question: {question}\n\n"
            "Assistant:"
        ),
    )
    chain = promptT | llm
    chat_history_str = format_chat_history(history)
    try:
        result = chain.invoke(
            {
                "chat_history": chat_history_str,
                "question": question,
                "plan": plan,
                "revision_context": revision_context,
            },
            config=config,
        )
        content = result.content if hasattr(result, "content") else str(result)
        return {"answer_chunks": [content]}
    except Exception as e:
        return {
            "error": str(e),
            "answer_chunks": ["Sorry, an error occurred while solving the question."],
        }

def review_needed_edge(state: DeepReasoningState) -> str:
    """
    Determine whether to loop back to planning or proceed to final answer.
    Caps at MAX_REVISION_LOOPS to prevent infinite revision loops.
    """
    review_loop_count = state.get("review_loop_count", 0)
    if review_loop_count >= MAX_REVISION_LOOPS:
        return "final_answer"
    review_needed = state.get("review_needed", False)
    return "plan" if review_needed else "final_answer"

def reviewer_node(state: DeepReasoningState, config: RunnableConfig) -> DeepReasoningState:
    """
    Review the answer and provide a final answer.
    """
    answer_chunks = state.get("answer_chunks") or []
    answer_str = "\n\n".join(answer_chunks) if answer_chunks else ""
    history = state.get("history") or []
    question = state["question"]
    plan = state["plan"]

    llm = initialize_llm()

    promptT = PromptTemplate(
        input_variables=["chat_history", "question", "answer", "plan"],
        template=(
            "You are a helpful assistant. Review whether the solver's answer is acceptable.\n\n"
            "If the solver correctly said they don't have the information (e.g. 'I don't know your name', 'You haven't shared it', 'I don't have access to that'), that is a valid final answer—output FINAL_ANSWER.\n\n"
            "Output REVISION_NEEDED only if the solver failed to answer the question when they could have (e.g. they had the info but didn't give it, or they gave a wrong answer).\n\n"
            "Reply with exactly one line: either 'FINAL_ANSWER' or 'REVISION_NEEDED'. Do not add long explanations.\n\n"
            "Plan: {plan}\n\n"
            "Answer: {answer}\n\n"
            "User question: {question}\n\n"
            "Assistant:"
        ),
    )
    chain = promptT | llm
    chat_history_str = format_chat_history(history)
    try:
        result = chain.invoke(
            {
                "chat_history": chat_history_str,
                "question": question,
                "answer": answer_str,
                "plan": plan,
            },
            config=config,
        )
        content = result.content if hasattr(result, "content") else str(result)
        # Only set review_needed; keep existing answer_chunks so final_answer has the solver's text
        revision_requested = "REVISION_NEEDED" in (content or "").upper()
        loop_count = state.get("review_loop_count", 0)
        # Cap revisions to avoid infinite loops
        if revision_requested and loop_count >= MAX_REVISION_LOOPS:
            revision_requested = False
        update = {"review_needed": revision_requested}
        if revision_requested:
            update["review_loop_count"] = loop_count + 1
            # Append this attempt (full plan and answer) so plan/solver see the actual earlier output
            prior = list(state.get("revision_attempts") or [])
            prior.append({
                "plan": (plan or "")[:MAX_REVISION_PLAN_CHARS],
                "answer": (answer_str or "")[:MAX_REVISION_ANSWER_CHARS],
                "verdict": (content or "").strip()[:200],
            })
            update["revision_attempts"] = prior
        return update
    except Exception as e:
        return {
            "error": str(e),
            "review_needed": False,
        }

def final_answer_node(state: DeepReasoningState, config: RunnableConfig) -> DeepReasoningState:
    """
    Provide the final answer.
    """
    answer_chunks = state.get("answer_chunks") or []
    answer_str = "\n\n".join(answer_chunks) if answer_chunks else ""
    history = state.get("history") or []
    question = state["question"]

    llm = initialize_llm()
    promptT = PromptTemplate(
        input_variables=["chat_history", "question", "answer_str"],
        template=(
            "You are a helpful assistant. Provide the final answer to the user in one or two clear sentences.\n\n"
            "If the answer is that you don't have the information (e.g. you don't know their name), say so plainly. Do not repeat long explanations or ask the user to 'proceed' or 'continue'.\n\n"
            "Answer chunks: {answer_str}\n\n"
            "User question: {question}\n\n"
            "Assistant:"
        ),
    )
    chain = promptT | llm
    chat_history_str = format_chat_history(history)
    try:
        result = chain.invoke(
            {
                "chat_history": chat_history_str,
                "question": question,
                "answer_str": answer_str,
            },
            config=config,
        )
        content = result.content if hasattr(result, "content") else str(result)
        return {"answer_chunks": [content]}
    except Exception as e:
        return {
            "error": str(e),
            "answer_chunks": ["Sorry, an error occurred while providing the final answer."],
        }   

graph = StateGraph(DeepReasoningState)
graph.add_node("plan", plan_node)
graph.add_node("solver", solver_node)
graph.add_node("reviewer", reviewer_node)
graph.add_node("final_answer", final_answer_node)
graph.add_conditional_edges("reviewer", review_needed_edge, ["plan", "final_answer"])
graph.set_entry_point("plan")
graph.add_edge("plan", "solver")
graph.add_edge("solver", "reviewer")
graph.add_edge("final_answer", END)

deep_reasoning_app = graph.compile()

__all__ = [
    "DeepReasoningState",
    "plan_node",
    "solver_node",
    "reviewer_node",
    "final_answer_node",
    "review_needed_edge",
    "deep_reasoning_app",
]