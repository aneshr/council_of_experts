# Test suite – Chat app

This directory contains the automated test suite for the chat app backend. Tests use **pytest** and **FastAPI’s TestClient**. External services (Ollama, Whisper, FAISS) are **mocked** so tests run without real backends.

---

## Quick start

**Full suite** (requires `langchain-env` with LangGraph and app deps installed):

```bash
conda activate langchain-env
cd chat_app
pip install -r requirements-langgraph.txt
pip install -r requirements-dev.txt
PYTHONPATH=. pytest tests/ -v
```

**Unit-only** (no LangGraph; models, helpers, RAG utils):

```bash
PYTHONPATH=. pytest tests/test_models.py tests/test_helper.py tests/test_rag.py -v
```

**With coverage:**

```bash
PYTHONPATH=. pytest tests/ -v --cov=app --cov=utils --cov=models --cov-report=term-missing
```

---

## Layout

| File | What it tests |
|------|----------------|
| **conftest.py** | Shared fixtures: `client` (TestClient), `sample_history`, `sample_chat_request`, `sample_chat_request_model`. Mocks `whisper` and `pydub` at import so the app can load without optional voice deps. The `client` fixture imports the FastAPI app only when used, so unit-only test runs don’t require LangGraph. |
| **test_models.py** | Pydantic models: **Message** (valid/invalid, missing fields) and **ChatRequest** (valid payloads, defaults, history from dicts, missing `question`, wrong type for `question`). |
| **test_helper.py** | **format_chat_history**: empty list, list of dicts, list of `Message`, system role, skipping empty content, mixed dict + Message. |
| **test_graph.py** | Router chat graph: **route_after_router** (next node: fallback vs stream_expert), **fallback_node** (fixed answer_chunks), **router_node** and **stream_expert_node** with mocked LLM/chain (no real Ollama). |
| **test_routes_chat.py** | API routes: **GET /api/v1/ask/** (200 + body), **POST /api/v1/ask/stream** (mocked graph stream, expert + fallback paths, 422 on missing question), **POST /api/v1/ask/voice-query** (mocked Whisper + graph, transcript + stream; 400 on invalid meta), **POST /api/v1/ask/byod** (mocked ingest_document, summary; 400 on empty file). |
| **test_rag.py** | RAG helpers: **_detect_file_type**, **_extract_text_from_txt**, **_extract_text** (txt/md, empty text, unsupported type), **_chunk_text** (splitting and single chunk). |

---

## Mocking strategy

- **Routes**  
  In route tests, `router_chat_app.stream` (and for voice-query: `convert_to_wav`, `initialize_whisper`) and for BYOD `ingest_document` are patched so no real LangGraph, Ollama, Whisper, or FAISS is used. The stream mock yields `(mode, chunk)` tuples in the shape the route expects (`"updates"` and `"messages"`).

- **Graph nodes**  
  In graph tests, `initialize_llm`, `router_expert`, `llm_response`, `chat_expert`, and `format_chat_history` are patched inside `app.graph.router_chat` so `router_node` and `stream_expert_node` run with fake return values and no network.

- **Optional deps**  
  `conftest.py` installs fake `whisper` and `pydub` in `sys.modules` before any app import so the app loads even when those packages are not installed.

---

## Test layers (by dependency)

```
test_models.py, test_helper.py, test_rag.py   →  No app/LangGraph (run anywhere)
test_graph.py                                  →  Needs app.graph (LangGraph)
test_routes_chat.py                            →  Needs app.main (FastAPI + graph)
```

Running only the first three files avoids importing the FastAPI app and LangGraph; the full suite requires the `langchain-env` environment.

---

## Adding tests

- **New route**: Add a test class in `test_routes_chat.py`; patch the graph or service used by that route (e.g. `router_chat_app`, `ingest_document`, `retrieve_context`).
- **New graph node or util**: Add or extend `test_graph.py` or `test_helper.py` / `test_rag.py`; mock any LLM, embeddings, or file I/O.
- **New shared fixture**: Put it in `conftest.py`.
