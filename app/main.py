"""
FastAPI application entrypoint.

This module creates the `FastAPI` app, configures CORS, sets up any
environment variables needed for external services, and includes
route modules (such as the chat router).
"""

# app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routes import chat  # , health

# from app.lifecycles import lifespan   # Example of how a lifespan handler could be wired

# Create the main FastAPI application instance.
app = FastAPI(
    title="Chatbot API",
    version="1.0.0",
    # lifespan=lifespan,  # ensures one-time init/cleanup if used
)

# CORS middleware.
# NOTE: You **cannot** use allow_credentials=True with a wildcard ("*") origin.
# For development, we explicitly allow the Vite dev server; for production,
# extend this list with your real frontend domains.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

"""
In FastAPI, `app.include_router()` is used to modularize your application.
It allows you to group related endpoints (routes) into separate files using
an `APIRouter`, and then include those routes in your main FastAPI app.
"""
# app.include_router(health.router, prefix="/api/v1", tags=["health"])
app.include_router(chat.router, prefix="/api/v1", tags=["chat"])
