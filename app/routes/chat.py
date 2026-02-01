from fastapi import APIRouter, Request
import time
from fastapi.responses import StreamingResponse
from utils.helper import stream_llm_response
import time
import requests
from utils.helper import chat_expert_1, chat_expert_2, chat_expert_3,initialize_llm, router_expert, llm_response
from models.chat_models import ChatRequest
import json
router = APIRouter(
    prefix="/ask",          # All routes here start with /users
    tags=["chat"],           # Group name in the docs
)



@router.get("/")
def list_users():
    
    return {"message": "this will give you full llm response"}

def get_expert_from_router(llm,question,expert_list):

    chain = router_expert(llm=llm,expert_list=expert_list,question=question)
    result = llm_response(chain,question=question)
    return result


@router.post("/stream")
async def stream_chat(request: ChatRequest):
    #body =  request.json()
    expert_list = [request.expert1,request.expert2,request.expert3] 
    question = request.question
    history = request.history
    expert1 = request.expert1
    expert2 = request.expert2
    expert3 = request.expert3
    
   # Here, you initialize your LLM or chain

    llm = initialize_llm()
    chosen_expert = get_expert_from_router(llm,question,expert_list)
    print(chosen_expert)
    expert_chain = {
        chosen_expert : chat_expert_1(llm,chosen_expert,question,history), # returns chain,question,chat_history
        # expert2 : chat_expert_2(llm,expert2,question,history),
        # expert3 : chat_expert_3(llm,expert3,question,history),
    }

    # e.g., LangChain or custom LLM

    def generate():
        for expert, chain in expert_chain.items():
            if expert == "None":
                continue
            
            #yield f"\n\n[{chain[0]} Expert]: \n\n"
            for chunk in stream_llm_response(chain, question, history):
                yield json.dumps({
                    "expert": expert,
                    "content": chunk
                }) + "\n" 

            yield json.dumps({
                "expert": expert,
                "event": "end"
            }) + "\n" 

    return StreamingResponse(generate(), media_type="text/plain")