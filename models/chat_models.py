from pydantic import BaseModel
from typing import List, Optional

class Message(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    question: str
    history: Optional[List[Message]] = []
    expert1: Optional[str] = "science"
    expert2: Optional[str] = "None"
    expert3: Optional[str] = "None"
