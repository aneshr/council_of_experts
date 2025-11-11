from fastapi import APIRouter
import time
from utils.helper import stream_llm_response
import time

router = APIRouter(
    prefix="/ask",          # All routes here start with /users
    tags=["chat"],           # Group name in the docs
)

@router.get("/")
def list_users():
    
    return {"message": "this will give you full llm response"}


@router.get("/stream")
def list_users():
    return {"message": "this will give you streaming llm response"}
