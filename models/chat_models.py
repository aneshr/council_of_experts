"""
Pydantic models shared between the FastAPI backend and the client.

These define the structure of:
- Individual chat messages.
- The request payload for the streaming chat endpoint.
"""

from pydantic import BaseModel
from typing import List, Optional


class Message(BaseModel):
    """
    Single chat message exchanged between the user and the assistant.

    Attributes
    ----------
    role : str
        Who sent the message (e.g. "user", "assistant", or expert name).
    content : str
        Natural‑language content of the message.
    """

    role: str
    content: str


class ChatRequest(BaseModel):
    """
    Request body for the `/api/v1/ask/stream` endpoint.

    Attributes
    ----------
    question : str
        Current user question.
    history : list[Message] | None
        Prior conversation messages. Defaults to an empty list.
    expert1, expert2, expert3 : str | None
        Names/labels of configured experts. `expert1` is typically required,
        while `expert2` and `expert3` may be "None" when unused.
    """

    question: str
    history: Optional[List[Message]] = []
    expert1: Optional[str] = "science"
    expert2: Optional[str] = "None"
    expert3: Optional[str] = "None"
