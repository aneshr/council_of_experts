from fastapi import APIRouter, Request
import time
from fastapi.responses import StreamingResponse
from utils.helper import stream_llm_response
import time
import requests
from utils.helper import chat_expert_1, chat_expert_2, chat_expert_3, init_credentials,initialize_llm
from models.chat_models import ChatRequest
router = APIRouter(
    prefix="/ask",          # All routes here start with /users
    tags=["chat"],           # Group name in the docs
)

@router.get("/")
def list_users():
    
    return {"message": "this will give you full llm response"}


@router.post("/stream")
async def stream_chat(request: ChatRequest):
    #body =  request.json()
    question = request.question
    history = request.history
    expert1 = request.expert1
    expert2 = request.expert2
    expert3 = request.expert3
    init_credentials()
    llm = initialize_llm()
    # Here, you initialize your LLM or chain
    expert_chain = {
        "expert1" : [expert1,chat_expert_1(llm,expert1,question,history)], # returns chain,question,chat_history
        "expert2" : [expert2,chat_expert_2(llm,expert2,question,history)],
        "expert3" : [expert3,chat_expert_3(llm,expert3,question,history)],
    }
    # e.g., LangChain or custom LLM

    def generate():
        for name, chain in expert_chain.items():
            if chain[0] == "None":
                continue
            yield f"\n\n--- {name} Expert ---\n\n"
            for chunk in stream_llm_response(chain[1], question, history):
                yield chunk
            yield "\n\n"   

    return StreamingResponse(generate(), media_type="text/plain")