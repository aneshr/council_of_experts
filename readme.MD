## Chat App – FastAPI + LangGraph + React

A FastAPI‑based backend and a modern React frontend for an **“experts council”** chat system with RAG, voice, and vision input. The system uses **LangGraph state machines** and LangChain to:

- Route questions to the most relevant expert.
- Stream expert answers token‑by‑token to the client.
- Ingest user documents into a FAISS index and answer questions with **RAG**.

## 📋 Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Configuration](#configuration)
- [Running the Server](#running-the-server)
- [Running the Frontend](#running-the-frontend)
- [API Endpoints](#api-endpoints)
- [Request/Response Formats](#requestresponse-formats)
- [Project Structure](#project-structure)
- [Dependencies](#dependencies)
- [Development](#development)
- [Troubleshooting](#troubleshooting)

## 🎯 Overview

This project implements:

1. **Multi‑expert chat** (`/api/v1/ask/stream`)
   - **User submits a question** → A LangGraph **router graph** (`router_chat_app`) picks the best expert label (e.g. *Science*, *Maths*).
   - **Expert generates response** → An expert‑specific LangChain chain produces the answer.
   - **Response is streamed** → Tokens are streamed back as newline‑delimited JSON for a great UX.
2. **Voice query** (`/api/v1/ask/voice-query`)
   - Accepts audio, converts to WAV, transcribes with **Whisper**, then reuses the same router + expert flow and streaming format.
3. **BYOD (Bring Your Own Data) RAG**
   - `/api/v1/ask/byod` ingests documents, extracts text, chunks, embeds with **OllamaEmbeddings**, and stores in a **FAISS** index.
   - `/api/v1/ask/byod-chat` uses a LangGraph‑backed RAG graph (`rag_chat_app`) to retrieve relevant chunks and stream **context‑grounded** answers.
4. **Vision chat (images)** (`/api/v1/ask/vision-query`)
   - Accepts an image plus optional text, runs a local **LLaVA** model via Ollama to summarize/analyze the image, then feeds that summary into the same LangGraph router graph used for text chat.
5. **React frontend (Vite)**
   - Located under `Frontend/`.
   - Provides a polished “Experts council” panel chat and a full BYOD upload + RAG chat UI.
   - Consumes the streaming endpoints and renders tokens as they arrive.

## 🏗️ Architecture

```
┌─────────────┐
│   Client    │  (Vite + React Frontend)
└──────┬──────┘
       │ HTTP POST /api/v1/ask/*
       │  (streaming NDJSON)
       ▼
┌───────────────────────────────────────────────┐
│                 FastAPI Backend               │
│  ┌─────────────────────────────────────────┐ │
│  │ app/main.py                            │ │
│  │  - CORS (Vite dev origins)             │ │
│  │  - Router registration                 │ │
│  └───────────────────────┬────────────────┘ │
│                          │                  │
│  ┌───────────────────────▼────────────────┐ │
│  │ app/routes/chat.py                     │ │
│  │  - /ask/stream, /ask/voice-query       │ │
│  │  - /ask/byod, /ask/byod-chat           │ │
│  └───────────────────────┬────────────────┘ │
│                          │                  │
│  ┌───────────────────────▼────────────────┐ │
│  │ app/graph/router_chat.py              │ │
│  │  - LangGraph router graph             │ │
│  │  - Chooses expert / fallback          │ │
│  └───────────────────────┬────────────────┘ │
│                          │                  │
│  ┌───────────────────────▼────────────────┐ │
│  │ app/graph/rag.py                      │ │
│  │  - LangGraph RAG chat graph           │ │
│  │  - (optional) ingest graph            │ │
│  └───────────────────────┬────────────────┘ │
│                          │                  │
│  ┌───────────────────────▼────────────────┐ │
│  │ utils/helper.py                        │ │
│  │  - LLM initialization (ChatOllama)     │ │
│  │  - History formatting                  │ │
│  └───────────────────────┬────────────────┘ │
│                          │                  │
│  ┌───────────────────────▼────────────────┐ │
│  │ utils/rag.py                          │ │
│  │  - Text extraction / chunking         │ │
│  │  - Embeddings + FAISS index           │ │
│  └────────────────────────────────────────┘ │
└───────────────────────────────────────────────┘
```

### Flow Diagram

1. **Client Request** → POST `/api/v1/ask/stream` with `ChatRequest` payload
2. **Router Selection** → `router_expert()` uses LLM to choose best expert; result is normalized (first line only). If the choice is not in the expert list or is `"None"`, the router is treated as uncertain.
3. **Expert Chain** → `chat_expert()` builds the domain-specific prompt chain for the chosen expert (or skipped when router returns `"None"`).
4. **Streaming** → When router chose an expert: `stream_llm_response()` yields tokens. When router chose `"None"`: a single Router message ("I am not sure...") is returned with no LLM call.
5. **Response** → JSON lines streamed back to client (`expert`, `content`; ends with `event: "end"`).

## 📦 Prerequisites

Before running the backend, ensure you have:

- **Python 3.10+** installed (to match the `langchain-env` conda setup).
- **Ollama** installed and running locally:
  - Download from: https://ollama.ai
  - Start the Ollama service: `ollama serve`
  - Pull the required model: `ollama pull gemma2:2b` (or your preferred model).
- **conda** (recommended) with a `langchain-env` environment that satisfies `requirements-langgraph.txt`.
- **Google Cloud credentials** (only if using the extra STT/TTS demos in `tempfilese/`).

## 🚀 Installation

### 1. Clone the Repository

```bash
git clone <repository-url>
cd chat_app
```

### 2. Create a Virtual Environment

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install fastapi uvicorn[standard]
pip install langchain langchain-community
pip install pydantic
pip install openai-whisper  # Optional: for speech-to-text
```

Or create a `requirements.txt` and install:

```bash
pip install -r requirements.txt
```

**Recommended `requirements.txt`:**

```txt
fastapi>=0.104.0
uvicorn[standard]>=0.24.0
langchain>=0.1.0
langchain-community>=0.0.20
pydantic>=2.0.0
openai-whisper>=20231117
python-multipart>=0.0.6
pydub>=0.25.0
```

### 4. Verify Ollama is Running

```bash
curl http://localhost:11434/api/tags
```

You should see a list of available models.

## ⚙️ Configuration

### Environment Variables

The backend currently uses hardcoded values in `app/main.py`. For production, move these to environment variables:

**Required:**
- `GOOGLE_API_KEY` - Google API key (if using Google services)
- `GOOGLE_APPLICATION_CREDENTIALS` - Path to Google service account JSON file

**Optional:**
- `OLLAMA_BASE_URL` - Defaults to `http://localhost:11434`
- `OLLAMA_MODEL` - Defaults to `gemma2:2b`

### CORS Configuration

The backend is configured to allow requests from the local Vite dev server:

- `http://localhost:5173`
- `http://localhost:5174`

Edit `app/main.py` to customize CORS settings (add your production domains here):

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:5174",
        "https://yourdomain.com",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

## 🏃 Running the Server

### Development Mode

```bash
conda activate langchain-env
cd chat_app
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The server will start at `http://localhost:8000`.

### Production Mode

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

### Using Docker (Optional)

You can still containerize the backend using a lightweight Dockerfile (not yet updated for `langchain-env`). For local development and interviews, running directly with `uvicorn` is usually simpler.

## 🖥️ Running the Frontend

The main frontend lives in the `Frontend/` directory and is built with **Vite + React**.

```bash
cd Frontend
npm install
npm run dev
```

By default Vite will start on `http://localhost:5173` or `http://localhost:5174`. The React app:

- Streams from `http://127.0.0.1:8000/api/v1/ask/stream` for the **Experts council** chat.
- Ingests documents via `http://127.0.0.1:8000/api/v1/ask/byod`.
- Runs RAG chat via `http://127.0.0.1:8000/api/v1/ask/byod-chat`.
- Sends voice queries via `http://127.0.0.1:8000/api/v1/ask/voice-query`.

Ensure the backend server is running before starting the frontend.

## 📡 API Endpoints

### Base URL

All endpoints are prefixed with `/api/v1`

### 1. Health Check

**GET** `/api/v1/ask/`

Simple test endpoint to verify the API is running.

**Response:**
```json
{
  "message": "this will give you full llm response"
}
```

### 2. Stream Chat

**POST** `/api/v1/ask/stream`

Main chat endpoint that streams expert responses.

**Request Body:**
```json
{
  "question": "What is quantum computing?",
  "history": [
    {
      "role": "user",
      "content": "Hello"
    },
    {
      "role": "assistant",
      "content": "Hi! How can I help?"
    }
  ],
  "experts": ["Science", "Mathematics"]
}
```

**Response Format:**

The endpoint returns a streaming response with `Content-Type: text/plain`. Each line is a JSON object:

```json
{"expert": "Science", "content": "Quantum"}
{"expert": "Science", "content": " computing"}
{"expert": "Science", "content": " is..."}
{"expert": "Science", "event": "end"}
```

### 3. Voice Query

**POST** `/api/v1/ask/voice-query`

Accepts recorded audio, transcribes it with Whisper, routes the transcribed text to the best expert, and streams the expert's response. Useful for hands-free or accessibility use cases.

**Request (multipart/form-data):**

- `audio`: UploadFile (required) – recorded audio (e.g. `.webm`, `.wav`, or other format supported by the backend after conversion to WAV).
- `meta`: JSON string (required) – same shape as `ChatRequest` for context:
  - `history`: array of `{ role, content }`
  - `experts`: array of expert labels (e.g. `["Science", "Mathematics"]`).

**Example (frontend FormData):**

```javascript
formData.append("audio", audioBlob, "query.webm");
formData.append("meta", JSON.stringify({
  history: llmHistory,
  experts: experts.filter(e => e && e !== "None")
}));
```

**Response format:**

Streamed `text/plain` with newline-delimited JSON:

1. First line: transcribed user question (so the UI can show what was said):
   ```json
   {"event": "transcript", "content": "What is photosynthesis?"}
   ```
2. Then the same expert stream as `/ask/stream`:
   ```json
   {"expert": "Science", "content": "..."}
   ...
   {"expert": "Science", "event": "end"}
   ```

**Notes:**

- The backend converts uploaded audio to WAV (via `pydub`) before sending to Whisper. Ensure `pydub` and `openai-whisper` are installed.

### 4. Vision Query (Images)

**POST** `/api/v1/ask/vision-query`

Accepts an image plus optional text, runs a local **LLaVA** vision model via Ollama to summarize/analyze the image, then routes the combined text through the same LangGraph router graph and streams the expert's response.

**Request (multipart/form-data):**

- `image`: UploadFile (required) – image file (e.g. `.png`, `.jpg`).
- `meta`: JSON string (required) with fields:
  - `question: str | null` – optional explicit question about the image.
  - `history: List[Message]` – prior conversation history.
  - `experts: List[str]` – expert labels (as in `/ask/stream`).
  - `mode: str` – optional hint such as `"general"`, `"ocr"`, `"diagram"`.

**Response format:**

Streamed `text/plain` with newline-delimited JSON:

1. First line: vision model summary of the image:

   ```json
   {"event": "vision_summary", "content": "<summary of the image>"}
   ```

2. Then the same expert stream as `/ask/stream`:

   ```json
   {"expert": "Science", "content": "..."}
   ...
   {"expert": "Science", "event": "end"}
   ```

### 5. BYOD Ingestion (RAG Index)

**POST** `/api/v1/ask/byod`

Ingest a user document into the global FAISS vector index for later retrieval.

**Request (multipart/form-data):**

```bash
curl -X POST "http://localhost:8000/api/v1/ask/byod" \
  -H "Accept: application/json" \
  -F "file=@/path/to/document.pdf" \
  -F "doc_name=Interview Notes" \
  -F "source=upload" \
  -F "tags=[\"interview\",\"guide\"]" \
  -F "description=My personal interview prep notes" \
  -F "language=en"
```

**Supported file types (for now):**

- `.txt`, `.md`
- `.pdf` (via `PyPDF2`)
- `.docx` (via `python-docx`)

**Successful response:**

```json
{
  "doc_id": "<uuid>",
  "doc_name": "Interview Notes",
  "filename": "document.pdf",
  "file_type": "pdf",
  "num_chunks": 24,
  "tags": ["interview", "guide"],
  "ingested_at": "2026-02-12T10:15:23Z"
}
```

### 6. BYOD RAG Chat

**POST** `/api/v1/ask/byod-chat`

Ask a question against the documents you have ingested. This endpoint:

- Loads the FAISS index.
- Retrieves the top-k relevant chunks using semantic similarity.
- Builds a RAG prompt with those chunks + chat history.
- Streams back an answer grounded in the document context.

**Request Body (same `ChatRequest` model):**

```json
{
  "question": "What are the main topics I should prepare for this interview?",
  "history": []
}
```

**Response Format:**

Newline-delimited JSON objects (no `expert` field; this endpoint is RAG-only):

```json
{"content": "You should focus on ..."}
{"content": " system design, "}
{"content": " APIs, and "}
{"content": " RAG architectures."}
{"event": "end"}
```

**Response Fields (BYOD-chat):**
- `content` (string): Token chunk from the LLM
- `event` (string, optional): `"end"` when the stream finishes; `"error"` with `detail` on failure

**Example cURL:**

```bash
curl -X POST "http://localhost:8000/api/v1/ask/stream" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "Explain photosynthesis",
    "history": [],
    "experts": ["Science"]
  }'
```

## 📝 Request/Response Formats

### ChatRequest Model

```python
{
  "question": str,                    # Required: User's question
  "history": List[Message],            # Optional: Previous messages
  "experts": List[str]                 # Optional: Defaults to ["science"]
}
```

### Message Model

```python
{
  "role": str,      # "user", "assistant", or expert name
  "content": str    # Message text
}
```

### Streaming Response Format

Each line in the stream is a JSON object (newline-delimited JSON):

```json
{"expert": "<expert_name>", "content": "<token_chunk>"}
{"expert": "<expert_name>", "content": "<token_chunk>"}
...
{"expert": "<expert_name>", "event": "end"}
```

## 📁 Project Structure

```
chat_app/
├── app/
│   ├── main.py              # FastAPI app initialization, CORS config
│   ├── graph/
│   │   ├── __init__.py      # router_chat graph wiring (LangGraph)
│   │   └── rag.py           # RAG LangGraph graphs (chat + ingest)
│   └── routes/
│       ├── __init__.py
│       └── chat.py          # Chat + BYOD endpoints (/ask/*)
├── models/
│   ├── __init__.py
│   └── chat_models.py       # Pydantic models (Message, ChatRequest)
├── utils/
│   ├── __init__.py
│   ├── helper.py            # LLM utilities, expert chains, streaming helpers
│   └── rag.py               # RAG helpers: ingestion, chunking, FAISS retrieval
├── Frontend/
│   ├── index.html           # Vite entry
│   └── src/
│       ├── App.jsx          # React SPA (Experts + BYOD)
│       └── index.css        # Main styling
├── rag_store/
│   └── faiss/               # On-disk FAISS index (created at runtime)
├── tests/                   # pytest-based test suite (backend)
├── requirements.txt         # Base Python dependencies
├── requirements-langgraph.txt  # LangGraph / LangChain / FAISS stack
└── requirements-dev.txt     # pytest + dev dependencies
```

### Key Files Explained

- **`app/main.py`**: FastAPI entry point, CORS setup, router registration.
- **`app/routes/chat.py`**: All `/api/v1/ask/*` endpoints: streaming chat, voice query, BYOD ingest, BYOD RAG chat.
- **`app/graph/__init__.py`** and **`app/graph/router_chat.py`**: LangGraph router graph (`router_chat_app`) that chooses experts and drives the main `/ask/stream` endpoint.
- **`app/graph/rag.py`**: LangGraph RAG graph (`rag_chat_app`) used by `/ask/byod-chat` (and an optional ingest graph).
- **`models/chat_models.py`**: Pydantic models for `Message` and `ChatRequest`.
- **`utils/helper.py`**: Core LLM helpers:
  - `initialize_llm()` – Creates the Ollama chat client.
  - `format_chat_history()` – Normalizes history into a prompt string.
  - `router_expert()` / `llm_response()` – Router chain + execution.
  - `chat_expert()` – Builds an expert-specific chain.
- **`utils/rag.py`**: RAG building blocks: text extraction, chunking, embeddings, FAISS index load/save.
- **`Frontend/src/App.jsx`**: React SPA that:
  - Streams multi‑expert answers from `/api/v1/ask/stream`.
  - Provides BYOD upload and RAG chat flows.
  - Sends voice queries to `/api/v1/ask/voice-query`.

## 📚 Dependencies

### Core Dependencies

- **FastAPI**: Modern web framework for building APIs
- **Uvicorn**: ASGI server for running FastAPI
- **LangChain**: Framework for building LLM applications
- **LangChain Community**: Community integrations (Ollama, FAISS, etc.)
- **Pydantic**: Data validation using Python type annotations
- **FAISS (faiss-cpu)**: Efficient similarity search for vector embeddings

### Optional / RAG & Voice Dependencies

- **PyPDF2**: PDF text extraction for `.pdf` ingestion
- **python-docx**: DOCX text extraction for `.docx` ingestion
- **OpenAI Whisper**: Speech-to-text for the `/ask/voice-query` endpoint (transcribes uploaded audio)
- **pydub**: Converts uploaded audio to WAV for Whisper in the voice-query flow
- **TTS**: Text-to-speech synthesis (if needed for future voice answers)

## 🔧 Development

### Running Tests

Use the **langchain-env** conda environment (required for LangGraph and full app imports):

```bash
conda activate langchain-env
cd chat_app
pip install -r requirements-langgraph.txt
pip install -r requirements-dev.txt
# From project root so app/ and utils/ are importable:
PYTHONPATH=. pytest tests/ -v
```

With coverage:

```bash
pytest tests/ -v --cov=app --cov=utils --cov=models --cov-report=term-missing
```

### Code Style

The codebase follows PEP 8 style guidelines. Consider using:

- **Black** for code formatting: `black .`
- **flake8** for linting: `flake8 .`
- **mypy** for type checking: `mypy .`

### API Documentation

FastAPI automatically generates interactive API documentation:

- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`
- **OpenAPI JSON**: `http://localhost:8000/openapi.json`

### Adding New Endpoints

1. Create route handlers in `app/routes/` (or add to existing files)
2. Register the router in `app/main.py`:
   ```python
   from app.routes import your_router
   app.include_router(your_router.router, prefix="/api/v1", tags=["your_tag"])
   ```

### Adding New Experts

1. Create a new expert function in `utils/helper.py`:
   ```python
   def chat_expert_4(llm, expertise, question, chat_history):
       # ... build prompt chain
       return chain
   ```

2. Import and use in `app/routes/chat.py`:
   ```python
   from utils.helper import chat_expert_4
   expert_chain[expert_name] = chat_expert_4(llm, expert_name, question, history)
   ```

## 🐛 Troubleshooting

### Ollama Connection Issues

**Error:** `Connection refused` or `Failed to connect to Ollama`

**Solution:**
- Ensure Ollama is running: `ollama serve`
- Check if the service is accessible: `curl http://localhost:11434/api/tags`
- Verify the model is pulled: `ollama list`

### CORS Errors

**Error:** `CORS policy: No 'Access-Control-Allow-Origin' header`

**Solution:**
- Check `app/main.py` CORS configuration
- Ensure your frontend URL is in `allow_origins`
- For development, you can temporarily use `allow_origins=["*"]`

### Model Not Found

**Error:** `Model 'gemma2:2b' not found`

**Solution:**
```bash
ollama pull gemma2:2b
# Or change the model in utils/helper.py initialize_llm()
```

### Streaming Issues

**Issue:** Response stops mid-stream or doesn't stream

**Solution:**
- Check network connectivity
- Verify the client is handling streaming correctly (not buffering)
- Check server logs for errors
- Ensure `StreamingResponse` is used correctly

### Import Errors

**Error:** `ModuleNotFoundError: No module named 'app'`

**Solution:**
- Run from the project root directory
- Ensure `app/` has `__init__.py` files
- Check Python path: `export PYTHONPATH="${PYTHONPATH}:$(pwd)"`

## 📄 License

[Add your license information here]

## 👥 Contributing

[Add contribution guidelines if applicable]

## 📞 Support

For issues or questions, please open an issue in the repository or contact the development team.

---

**Last Updated:** February 2026
