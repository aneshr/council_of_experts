"""
Chat-related FastAPI routes.

This router exposes endpoints for:
- A simple health/test endpoint at `/ask/`.
- A streaming chat endpoint at `/ask/stream` that:
  * Routes a question to the most relevant expert.
  * Streams the expert's LLM response back to the client as JSON lines.
- A BYOD ingestion endpoint at `/ask/byod` that:
  * Accepts document uploads and metadata.
  * Extracts, chunks, and indexes text into a global FAISS store.
"""


from fastapi import APIRouter, Request, UploadFile, File, Form, HTTPException
import time
from fastapi.responses import StreamingResponse
from utils.helper import stream_llm_response
import time
import requests
from utils.helper import (
    chat_expert_1,
    chat_expert_2,
    chat_expert_3,
    initialize_llm,
    router_expert,
    llm_response,
    convert_to_wav,
    initialize_whisper,
    format_chat_history,
)
from models.chat_models import ChatRequest
from utils.rag import ingest_document, retrieve_context
import json
import os
print("Chat routes file:",__file__)
# Router configuration – all routes in this module will be mounted under /ask.
router = APIRouter(
    prefix="/ask",          # All routes here start with /ask
    tags=["chat"],          # Group name in the OpenAPI docs
)


@router.get("/")
def list_users():
    """
    Simple test/placeholder endpoint.

    Currently just returns a static JSON payload describing the endpoint.
    """
    return {"message": "this will give you full llm response"}


def get_expert_from_router(llm, question, expert_list):
    """
    Use the router LLM to choose the most relevant expert for a question.

    Parameters
    ----------
    llm :
        LLM instance used for routing.
    question : str
        User question that needs to be routed.
    expert_list : list[str]
        List of available expert names.
    """
    chain = router_expert(llm=llm, expert_list=expert_list, question=question)
    result = llm_response(chain, question=question)
    return result


@router.post("/stream")
async def stream_chat(request: ChatRequest):
    """
    Main chat endpoint – streams expert responses back to the client.

    Request body is validated against `ChatRequest` and contains:
    - `question`: current user question.
    - `history`: prior messages (role + content).
    - `expert1`, `expert2`, `expert3`: expert names.

    The server:
    1. Initializes the underlying LLM.
    2. Uses the router chain to pick the most relevant expert.
    3. Builds an expert-specific chain.
    4. Streams JSON lines back to the caller, where each line has:
       `{ "expert": <name>, "content": <chunk> }`
       and finally an `{ "event": "end" }` marker per expert.
    """
    # Collect all experts from the validated request model.
    expert_list = [request.expert1, request.expert2, request.expert3]
    question = request.question
    history = request.history
    expert1 = request.expert1
    expert2 = request.expert2
    expert3 = request.expert3
    
    # Here, you initialize your LLM or chain.
    llm = initialize_llm()

    # Ask the router which expert should handle this question.
    chosen_expert = get_expert_from_router(llm, question, expert_list)
    print(chosen_expert)

    # Build a mapping of expert name -> expert chain.
    # For now only the chosen expert is active; others are commented out.
    expert_chain = {
        # returns chain,question,chat_history
        chosen_expert: chat_expert_1(llm, chosen_expert, question, history),
        # expert2 : chat_expert_2(llm,expert2,question,history),
        # expert3 : chat_expert_3(llm,expert3,question,history),
    }

    # e.g., LangChain or custom LLM
    def generate():
        """
        Generator that yields JSON lines encoded as UTF‑8 text.

        Each expert's response is streamed chunk by chunk using
        `stream_llm_response`, and we tag each chunk with the expert name.
        """
        for expert, chain in expert_chain.items():
            if expert == "None":
                # Skip placeholder/disabled experts.
                continue
            
            # yield f"\n\n[{expert} Expert]: \n\n"
            for chunk in stream_llm_response(chain, question, history):
                yield json.dumps(
                    {
                        "expert": expert,
                        "content": chunk,
                    }
                ) + "\n"

            # Signal that this expert has finished streaming.
            yield json.dumps(
                {
                    "expert": expert,
                    "event": "end",
                }
            ) + "\n"

    # StreamingResponse ensures the HTTP connection stays open while
    # `generate()` yields chunks.
    return StreamingResponse(generate(), media_type="text/plain")


@router.post("/voice-query")
async def voice_query(audio: UploadFile = File(...), meta: str = Form(...)):
    """
    Voice query endpoint – accepts recorded audio plus metadata, transcribes
    the audio to text, routes the query to the best expert, and streams the
    expert's response back to the client.

    Frontend example (FormData):
        formData.append("audio", audioBlob, "query.webm");
        formData.append(
            "meta",
            JSON.stringify({
              history: llmHistory,
              expert1: experts.expert1,
              expert2: experts.expert2,
              expert3: experts.expert3
            })
        );
    """
    # Get the raw audio bytes and metadata from the request
    audio_bytes = audio.file.read()
    meta = json.loads(meta)

    # Always convert the uploaded audio to a proper WAV file on disk.
    # `convert_to_wav` returns the path to a temporary WAV file.
    wav_path = convert_to_wav(audio_bytes)
    
    # Transcribe the audio from the WAV file
    whisper_model = initialize_whisper()
    segments = whisper_model.transcribe(audio=wav_path, language="en", beam_size=5)
    print("segments:", segments)
    prompt = segments["text"]
    # import llm
    llm = initialize_llm()
    # Get the expert from the router
    expert_list = [meta["expert1"], meta["expert2"], meta["expert3"]]
    expert = get_expert_from_router(llm, prompt, expert_list)
    print(expert)
    
    # Build the expert chain
    expert_chain = {
        expert: chat_expert_1(llm, expert, prompt, meta["history"])
    }
    
    # Stream the expert response (same JSON-lines format as /stream)
    def generate():
        # First send the transcribed text so the frontend can display the
        # actual user question instead of a generic \"Voice question\" label.
        yield json.dumps(
            {
                "event": "transcript",
                "content": prompt,
            }
        ) + "\n"

        # Then stream the expert's answer as normal.
        for expert, chain in expert_chain.items():
            if expert == "None":
                continue
            for chunk in stream_llm_response(chain, prompt, meta["history"]):
                yield json.dumps(
                    { 
                        "expert": expert,
                        "content": chunk,
                    }
                ) + "\n"
            yield json.dumps(
                {
                    "expert": expert,
                    "event": "end",
                }
            ) + "\n"
    return StreamingResponse(generate(), media_type="text/plain")

@router.post("/byod")
async def byod(
    file: UploadFile = File(...),
    doc_name: str | None = Form(None),
    source: str = Form("upload"),
    tags: str | None = Form(None),
    description: str | None = Form(None),
    language: str = Form("en"),
):
    """
    BYOD ingestion endpoint.

    Accepts a single uploaded file plus optional metadata, extracts text,
    chunks it, embeds with a local Ollama embedding model, and upserts
    into a global FAISS index.

    Request (multipart/form-data):
    - file: UploadFile (required)
    - doc_name: str (optional)
    - source: str (optional, default "upload")
    - tags: str (optional; comma-separated list or JSON array)
    - description: str (optional)
    - language: str (optional, default "en")
    """
    try:
        file_bytes = await file.read()
        if not file_bytes:
            raise HTTPException(status_code=400, detail="Uploaded file is empty.")

        # Parse tags: allow either JSON array or comma-separated string.
        parsed_tags = []
        if tags:
            import json

            raw = tags.strip()
            if raw:
                try:
                    maybe_list = json.loads(raw)
                    if isinstance(maybe_list, list):
                        parsed_tags = [str(t) for t in maybe_list]
                    else:
                        parsed_tags = [str(maybe_list)]
                except json.JSONDecodeError:
                    parsed_tags = [t.strip() for t in raw.split(",") if t.strip()]

        summary = ingest_document(
            file_bytes=file_bytes,
            filename=file.filename,
            doc_name=doc_name,
            source=source,
            tags=parsed_tags,
            description=description,
            language=language,
        )

        return summary

    except ValueError as e:
        # Validation / unsupported types / empty text, etc.
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        # Re-raise FastAPI HTTPExceptions unchanged.
        raise
    except Exception as e:
        # Unexpected errors – avoid leaking internals.
        print("Error in /ask/byod:", e)
        raise HTTPException(
            status_code=500,
            detail="Failed to ingest document. Please try again later.",
        )


@router.post("/byod-chat")
async def byod_chat(request: ChatRequest):
    """
    RAG-aware chat endpoint over ingested BYOD documents.

    Reuses the ChatRequest model:
    - question: str
    - history: List[Message]

    Flow:
    1. Retrieve top-k relevant chunks from FAISS.
    2. Build a RAG prompt using those chunks + chat history.
    3. Stream the answer back as newline-delimited JSON lines:
       {"content": "<chunk>"} ... {"event": "end"}
    """
    question = request.question
    history = request.history or []

    try:
        # Step 1: retrieve relevant context from FAISS
        docs = retrieve_context(question, k=5)

        # Build a readable context block with simple citations.
        context_parts = []
        for i, d in enumerate(docs):
            meta = d.metadata or {}
            label = meta.get("doc_name") or meta.get("filename") or f"doc-{i+1}"
            context_parts.append(
                f"[{i+1}] ({label})\n{d.page_content.strip()}"
            )
        context_str = "\n\n---\n\n".join(context_parts)

    except ValueError as e:
        # No index or other retrieval issues – return a clear 400.
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        print("Error during RAG retrieval:", e)
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve context from the document index.",
        )

    # Step 2: build a simple RAG prompt chain.
    llm = initialize_llm()

    from langchain.prompts import PromptTemplate

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

    def generate():
        """
        Stream the RAG answer as newline-delimited JSON objects.
        """
        full_history = format_chat_history(history)
        try:
            for chunk in chain.stream(
                {
                    "chat_history": full_history,
                    "question": question,
                    "context": context_str,
                }
            ):
                yield json.dumps({"content": chunk.content}) + "\n"

            yield json.dumps({"event": "end"}) + "\n"
        except Exception as e:
            print("Error streaming RAG response:", e)
            # Best-effort error notification to the client.
            yield json.dumps(
                {
                    "event": "error",
                    "detail": "Error while streaming RAG response.",
                }
            ) + "\n"

    return StreamingResponse(generate(), media_type="text/plain")

