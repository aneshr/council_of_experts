# Chat App - FastAPI Backend

A FastAPI-based backend service that provides an intelligent chat interface with expert routing capabilities. The system uses an LLM router to select the most relevant expert for each question and streams responses back to the client in real-time.

## 📋 Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Configuration](#configuration)
- [Running the Server](#running-the-server)
- [API Endpoints](#api-endpoints)
- [Request/Response Formats](#requestresponse-formats)
- [Project Structure](#project-structure)
- [Dependencies](#dependencies)
- [Development](#development)
- [Troubleshooting](#troubleshooting)

## 🎯 Overview

This FastAPI backend implements a multi-expert chat system where:

1. **User submits a question** → The system routes it to the most relevant expert using an LLM router
2. **Expert generates response** → The chosen expert's LLM chain processes the question with conversation context
3. **Response is streamed** → Tokens are sent back to the client in real-time as JSON lines

The backend is designed to work with a React frontend (or any HTTP client) and supports streaming responses for a smooth user experience.

## 🏗️ Architecture

```
┌─────────────┐
│   Client    │ (React Frontend)
│  (React)    │
└──────┬──────┘
       │ HTTP POST /api/v1/ask/stream
       │
       ▼
┌─────────────────────────────────────┐
│      FastAPI Backend                │
│  ┌───────────────────────────────┐ │
│  │  app/main.py                  │ │
│  │  - CORS Configuration          │ │
│  │  - Router Registration         │ │
│  └───────────┬───────────────────┘ │
│              │                     │
│  ┌───────────▼───────────────────┐ │
│  │  app/routes/chat.py           │ │
│  │  - /ask/stream endpoint       │ │
│  │  - Request validation         │ │
│  └───────────┬───────────────────┘ │
│              │                     │
│  ┌───────────▼───────────────────┐ │
│  │  utils/helper.py              │ │
│  │  - LLM initialization         │ │
│  │  - Expert routing             │ │
│  │  - Response streaming         │ │
│  └───────────┬───────────────────┘ │
│              │                     │
│  ┌───────────▼───────────────────┐ │
│  │  Ollama LLM (localhost:11434)  │ │
│  └────────────────────────────────┘ │
└─────────────────────────────────────┘
```

### Flow Diagram

1. **Client Request** → POST `/api/v1/ask/stream` with `ChatRequest` payload
2. **Router Selection** → `router_expert()` uses LLM to choose best expert
3. **Expert Chain** → `chat_expert_1/2/3()` builds domain-specific prompt chain
4. **Streaming** → `stream_llm_response()` yields tokens as they're generated
5. **Response** → JSON lines streamed back to client

## 📦 Prerequisites

Before running the backend, ensure you have:

- **Python 3.8+** installed
- **Ollama** installed and running locally
  - Download from: https://ollama.ai
  - Start the Ollama service: `ollama serve`
  - Pull the required model: `ollama pull gemma2:2b` (or your preferred model)
- **Google Cloud credentials** (if using Google services)
  - Service account JSON file for speech-to-text functionality

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

The backend is configured to allow requests from:
- `http://localhost:5173` (Vite dev server)
- All origins (`*`) - **⚠️ Restrict this in production**

Edit `app/main.py` to customize CORS settings:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "https://yourdomain.com"],
    allow_methods=["*"],
    allow_headers=["*"],
)
```

## 🏃 Running the Server

### Development Mode

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The server will start at `http://localhost:8000`

### Production Mode

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

### Using Docker (Optional)

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

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
  "expert1": "Science",
  "expert2": "Mathematics",
  "expert3": "None"
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

**Response Fields:**
- `expert` (string): Name of the expert generating the response
- `content` (string): Token chunk from the LLM
- `event` (string, optional): `"end"` when the expert finishes streaming

**Example cURL:**

```bash
curl -X POST "http://localhost:8000/api/v1/ask/stream" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "Explain photosynthesis",
    "history": [],
    "expert1": "Science",
    "expert2": "None",
    "expert3": "None"
  }'
```

## 📝 Request/Response Formats

### ChatRequest Model

```python
{
  "question": str,                    # Required: User's question
  "history": List[Message],            # Optional: Previous messages
  "expert1": str,                      # Optional: Default "science"
  "expert2": str,                      # Optional: Default "None"
  "expert3": str                       # Optional: Default "None"
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
│   └── routes/
│       ├── __init__.py
│       └── chat.py          # Chat endpoints (/ask/*)
├── models/
│   ├── __init__.py
│   └── chat_models.py       # Pydantic models (Message, ChatRequest)
├── utils/
│   ├── __init__.py
│   └── helper.py            # LLM utilities, expert chains, streaming
├── README.md                # This file
└── requirements.txt         # Python dependencies
```

### Key Files Explained

- **`app/main.py`**: FastAPI application entry point, middleware setup, router registration
- **`app/routes/chat.py`**: Chat endpoints, request handling, streaming logic
- **`models/chat_models.py`**: Pydantic models for request/response validation
- **`utils/helper.py`**: Core LLM functions:
  - `initialize_llm()` - Creates Ollama client
  - `router_expert()` - Builds routing chain
  - `chat_expert_1/2/3()` - Builds expert-specific chains
  - `stream_llm_response()` - Streams tokens from LLM
  - `format_chat_history()` - Converts message list to prompt string

## 📚 Dependencies

### Core Dependencies

- **FastAPI**: Modern web framework for building APIs
- **Uvicorn**: ASGI server for running FastAPI
- **LangChain**: Framework for building LLM applications
- **LangChain Community**: Community integrations (Ollama support)
- **Pydantic**: Data validation using Python type annotations

### Optional Dependencies

- **OpenAI Whisper**: Speech-to-text transcription
- **TTS**: Text-to-speech synthesis (if needed)

## 🔧 Development

### Running Tests

```bash
# Install test dependencies
pip install pytest pytest-asyncio httpx

# Run tests
pytest
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
