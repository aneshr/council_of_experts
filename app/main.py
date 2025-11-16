# app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routes import chat#, health
import os
#from app.lifecycles.py import lifespan

os.environ["GOOGLE_API_KEY"] = "AIzaSyCWtb1Al9r8LtGxn-2stZvUBL732wGWwTM"
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "/Users/aneesh/Work/chat_app/speech.json"

app = FastAPI(
    title="Chatbot API",
    version="1.0.0",
    #lifespan=lifespan,  # ensures one-time init/cleanup
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten in prod
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

'''
In FastAPI, app.include_router() is used to modularize your application.
It allows you to group related endpoints (routes) into separate files using a Router object,
and then include those routes in your main FastAPI app.
'''
#app.include_router(health.router, prefix="/api/v1", tags=["health"])
app.include_router(chat.router,   prefix="/api/v1", tags=["chat"])
