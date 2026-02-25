## Chat App – Interview Prep Guide

This document is designed to help you **explain this project in interviews** – from a 30–60 second elevator pitch, to deeper architecture and design questions.

---

### 1. High‑Level Elevator Pitch

- **What this project is**
  - A **FastAPI + LangGraph backend** and a **Vite + React frontend** that power an **“experts council” chat system** plus a BYOD RAG mode.
  - A user asks a question; a **LangGraph router state machine** picks the best expert; that expert’s LangChain chain generates and **streams** the answer token‑by‑token to the client.
  - Users can also **upload their own documents**, which are indexed into FAISS and queried via a **RAG graph**, and they can send **voice queries** that are transcribed with Whisper and routed through the same pipeline.

- **One‑liner you can say**
  - “I built a FastAPI + LangGraph multi‑expert chat system with a modern React frontend. A router graph chooses the best expert per question, answers are streamed in real time, and there’s a BYOD RAG mode plus voice queries on top of a local Ollama + FAISS stack.”

---

### 2. Tech Stack Overview

- **Backend**
  - **FastAPI** for the HTTP API.
  - **uvicorn** as the ASGI server.
  - **Pydantic** models for request validation (`Message`, `ChatRequest`).
  - **LangChain** / `langchain_community` with `ChatOllama` as the LLM client.
  - **LangGraph** for orchestrating flows as explicit state machines:
    - `router_chat_app` (expert router graph).
    - `rag_chat_app` (RAG answer graph).
  - Local LLM + embeddings served by **Ollama** (e.g. `gemma2:2b` for chat, `nomic-embed-text` for embeddings).
  - **FAISS** (via LangChain) as the on-disk vector store for Retrieval‑Augmented Generation (RAG).

- **Frontend / UI**
  - **Vite + React** SPA in `Frontend/`:
    - “Experts council” chat that streams expert responses from `/api/v1/ask/stream`.
    - “Your documents (BYOD)” mode for upload + RAG chat over ingested docs.
    - Voice query button that records audio and calls `/api/v1/ask/voice-query`.
  - (Legacy prototypes: some Streamlit UIs still exist in `tempfilese/`, but the main UI is now React.)

- **Speech & Audio**
  - **Backend voice-query**: `openai-whisper` (small model) and `pydub` in the main FastAPI app (`app/routes/chat.py` → `utils/helper.py`). The `/ask/voice-query` endpoint accepts uploaded audio, converts to WAV, transcribes with Whisper, then runs the same router + expert flow and streams the response (with an initial `transcript` event).
  - Additional demos: `whisper` / `faster_whisper` in older scripts (`speechtotext.py`, `sp-to-txt.py`); `TTS` in `texttospeech.py` and `chat_llm.py`.

---

### 3. Backend Architecture (FastAPI + LLM Router + RAG)

#### 3.1 Main Application Setup – `app/main.py`

- **Responsibilities**
  - Create the `FastAPI` app instance.
  - Configure **CORS** so that a local frontend (e.g. Vite on `http://localhost:5173`) can call the API.
  - Wire up routers – specifically the chat routes from `app/routes/chat.py`.
  - Set up environment for external providers (currently hard‑coded; should become real env vars in production).

- **Key points to mention**
  - You understand **CORS** and why you restrict origins in production.
  - You know that **secrets should not be hard‑coded**; instead they should come from environment variables or a secrets manager.

#### 3.2 Routing Layer – `app/routes/chat.py`

- **Router configuration**
  - Uses `APIRouter` with:
    - `prefix="/ask"` – all endpoints under `/api/v1/ask/*`.
    - `tags=["chat"]` – groups them in the FastAPI docs.
 
- **Core chat endpoint**
  - `GET /api/v1/ask/`
    - Simple health/test endpoint returning a static JSON message.
  - `POST /api/v1/ask/stream`
    - Main **streaming chat endpoint**.
    - Accepts a `ChatRequest` body with:
      - `question: str`
      - `history: List[Message]`
      - `experts: List[str]`: expert labels (e.g. `["Science", "Mathematics"]`).

- **Flow inside `/stream` (LangGraph‑based)**
  1. Build an initial state `{ question, history, expert_list }`.
  2. Call `router_chat_app.stream(initial_state, stream_mode=["updates", "messages"])`.
  3. Handle **updates**:
     - Router node sets `chosen_expert` and may emit router events.
     - If `chosen_expert == "None"`, a fallback node sets `answer_chunks` to a clarification message; the route treats this as a “Router” answer.
  4. Handle **messages**:
     - When the graph is in the `stream_expert` node, LangGraph streams LLM tokens via `stream_mode="messages"`.
     - The route converts each chunk into NDJSON:  
       `{"expert": "<chosen_expert>", "content": "<token_chunk>"}`.
  5. At the end of the stream, the route emits a final `{"expert": "<chosen_expert>", "event": "end"}` line and closes the `StreamingResponse`.

- **Talking point (design choice)**
  - Using **LangGraph** lets you model routing and fallback logic as explicit nodes/edges, while `StreamingResponse` still gives the client low‑latency token streaming.

#### 3.3 BYOD + RAG Endpoints

You also have a **Bring Your Own Data** (BYOD) flow that turns user documents into a searchable knowledge base, then answers questions grounded in those documents.

- `POST /api/v1/ask/byod`
  - Ingestion endpoint.
  - Accepts `multipart/form-data` with:
    - `file`: the uploaded document (`.txt`, `.md`, `.pdf`, `.docx`).
    - Optional `doc_name`, `source`, `tags`, `description`, `language`.
  - Internally:
    - Extracts raw text using format-specific libraries (`PyPDF2`, `python-docx`, plain decoding).
    - Splits text into overlapping chunks.
    - Embeds each chunk using `OllamaEmbeddings(model="nomic-embed-text")`.
    - Stores embeddings + metadata in a global **FAISS** index on disk (`rag_store/faiss`).
  - Returns a summary JSON: `doc_id`, `filename`, `file_type`, `num_chunks`, `tags`, `ingested_at`.

- `POST /api/v1/ask/byod-chat`
  - RAG chat endpoint.
  - Reuses the same `ChatRequest` model (`question`, `history`).
  - Flow:
    1. Embeds the **question** and runs `similarity_search` on the FAISS index to get top‑k relevant chunks.
    2. Builds a context block from those chunks, including simple citations (e.g. `[1] (Interview Notes) ...`).
    3. Builds a RAG prompt: system instructions + document context + formatted chat history + current question.
    4. Streams the answer using `StreamingResponse` as newline-delimited JSON:
       - `{"content": "<token_chunk>"}` …
       - Final `{"event": "end"}`.

**Interview angle:**

- You can now describe **two parallel flows**:
  - Expert‑routed chat over general knowledge (`/stream`).
  - RAG‑based chat grounded in user documents (`/byod` + `/byod-chat`).
- Emphasize that:
  - Embeddings are computed **once at ingestion time**.
  - Query-time retrieval is very fast thanks to FAISS.
  - Answers are explicitly **grounded in retrieved context**, and the prompt tells the model to say “I don’t know” when the docs don’t support the answer.

#### 3.4 Data Models – `models/chat_models.py`

- `Message`
  - Represents a single chat message with:
    - `role: str` – `"user"`, `"assistant"`, or expert name.
    - `content: str` – the text of the message.

- `ChatRequest`
  - Request model for `/api/v1/ask/stream`.
  - Contains:
    - `question: str`
    - `history: Optional[List[Message]] = []`
    - `experts: List[str] = ["science"]`

- **Talking point**
  - Using **Pydantic** gives you:
    - Type‑safe request parsing.
    - Automatic validation and error responses.
    - Clear, versionable contracts shared with the frontend.

---

### 4. LLM Utilities & Expert Chains – `utils/helper.py`

This module holds the core LLM logic: initializing the LLM, building prompts, routing, and streaming.

#### 4.1 LLM Initialization – `initialize_llm`

- Uses `ChatOllama` to talk to a **local Ollama server**.
- Configured with:
  - `model_name` (default `"gemma2:2b"`).
  - `base_url="http://localhost:11434"`.

**Interview angle:** you can discuss why you chose a **local LLM (Ollama)** – privacy, cost, offline capability – vs. a remote API.

#### 4.2 History Formatting – `format_chat_history`

- Accepts a mixed list of:
  - Pydantic objects with `.role`/`.content`.
  - Dicts with `"role"` / `"content"`.
- Normalizes these into lines like:
  - `"User: ..."`
  - `"Assistant: ..."`
  - `"System: ..."`
- Crucial for **prompt engineering** because it feeds the conversation context into downstream chains.

#### 4.3 Streaming Responses – `stream_llm_response`

- Receives a `chain`, a `question`, and `history`.
- Calls `chain.stream({"chat_history": ..., "question": ...})`.
- Accumulates `response` but also:
  - `yield`s `chunk.content` token by token.
  - Adds a small `time.sleep(0.05)` to smooth streaming.

**Key idea to explain:**
- This function is a **bridge** between LangChain’s streaming API and FastAPI’s `StreamingResponse`.
- It gives you **fine‑grained control** over how you stream tokens and how they are chunked to the client.

#### 4.4 Router Chain – `router_expert`

- Builds a `PromptTemplate` instructing the model:
  - “You are an expert router.”
  - Lists `expert_list`.
  - Enforces rules such as:
    - “Choose exactly ONE expert.”
    - “Return ONLY the expert name.”
    - “If uncertain, choose \"None\".”
- Composes the prompt with the LLM via `promptT | llm` to create a chain.
- **In the route**: The raw router output is normalized—only the **first line** is used as the expert name. If that name is not in the expert list (e.g. the model added extra text or said "None"), it is treated as `"None"` and the backend returns a single Router fallback message without calling the expert LLM.

**Conceptual explanation for interviews:**
- You treat the LLM as a **classifier / router** that maps:
  - Input: `(question, list_of_experts)`
  - Output: **single expert label**.
- This is a form of **tool routing / mixture‑of‑experts**, implemented purely via prompting rather than custom ML training.

#### 4.5 Expert Chain – `chat_expert`

- A single function `chat_expert(llm, expertise, question, chat_history)`:
  - Creates a `PromptTemplate` with:
    - `"You are an expert in {expertise}."`
    - Formatted `chat_history` and `"User: {question}"`.
  - Pipes the prompt into `llm` to create a chain (`promptT | llm`).
  - Returns the chain for the given expert name (e.g. "Science", "Maths"). The route uses this for whichever expert the router selected; no separate per-expert functions are needed.
**Potential future improvement to mention:**
- Use **different models or parameters per expert** (e.g. one small fast model for simple questions, a larger one for complex reasoning).

#### 4.6 Summarizer & Speech Helpers

- `summarizer(...)`:
  - Builds a summarization chain that:
    - Reads the full conversation.
    - Mentions what each expert contributed.
    - Produces a concise answer (< 20 words).
- `initiaize_whisper()`:
  - Loads a base Whisper model for ASR.
  - Used in speech‑related scripts.

These functions show you understand **compositional LLM workflows** (chat + summarization + speech) rather than just a single raw LLM call.

---

### 5. Frontend & Streaming Client – React SPA

The primary client is a **Vite + React** single-page app in `Frontend/src/App.jsx` that talks to the FastAPI backend.

- **Page state**
  - Maintains:
    - `messages`: chat history for the Experts council mode.
    - `llmHistory`: history actually sent to the backend.
    - `experts: string[]`: dynamic list of expert labels (defaults to three, user can add more).
    - Separate state for BYOD chat and upload (BYOD mode).
    - State for voice recording and vision (image) uploads.

- **Welcome screen**
  - “How would you like to chat?” choice:
    - **Experts council** mode (multi‑expert chat).
    - **Your documents (BYOD)** mode (RAG over uploaded docs).
  - Experts setup form:
    - Renders one input per expert in the `experts` array.
    - Includes a **“+ Add expert”** button to add more experts dynamically.

- **Experts chat screen**
  - Shows expert chips for all non‑`"None"` experts.
  - Renders history with user/assistant/system bubbles and per‑expert labels.
  - Input bar:
    - Text input bound to `input`.
    - File input for attaching an image (vision questions).
    - Single **Send** button:
      - If an image is attached → calls `/api/v1/ask/vision-query`.
      - Otherwise → calls `/api/v1/ask/stream`.
  - Streaming handling:
    - Reads the NDJSON stream from the backend.
    - Ignores router‑only messages (`expert === "Router"`).
    - Maintains a single assistant bubble per turn and appends token chunks as they arrive.

- **BYOD chat screen**
  - Provides an upload card that posts to `/api/v1/ask/byod`.
  - After ingestion, BYOD chat sends text questions to `/api/v1/ask/byod-chat` and streams RAG answers.

- **Voice input**
  - Uses the browser `MediaRecorder` API to capture audio.
  - Sends audio + `meta` (history + experts) to `/api/v1/ask/voice-query`.
  - Handles the initial `"transcript"` event and then streams expert responses like `/ask/stream`.

**Interview angle:**
- You can explain both sides of streaming:
  - **Server**: generator + `StreamingResponse` emitting NDJSON lines.
  - **Client**: `ReadableStream` reader that incrementally decodes lines and updates React state to render streaming text.

---

### 6. Additional Experiments & Utilities

These files are experimental or demo‑style, but they are useful talking points:

- **`chat_llm.py`**
  - Streamlit app that:
    - Uses `ChatGoogleGenerativeAI` (e.g. Gemini) directly instead of Ollama.
    - Supports:
      - Audio input via microphone (`streamlit_mic_recorder`).
      - Whisper STT to convert speech to text.
      - Multiple experts and a summarizer chain.
      - Text‑to‑speech playback using `TTS`.
  - Shows you can **mix LLMs, STT, and TTS** in a single conversational experience.

- **`speechtotext.py` / `sp-to-txt.py`**
  - Demonstrate using Whisper or `faster_whisper` to transcribe audio files.
  - Good to mention when talking about **media processing** or **multimodal** features.

- **`texttospeech.py`**
  - Minimal TTS demo using `TTS` library.

- **Root `main.py`**
  - Early / experimental Streamlit + CORS snippet.
  - Core backend entry point is `app/main.py` (clarify this in interviews).

---

### 7. Common Interview Questions & How to Answer

#### 7.1 “Walk me through the architecture of this project.”

**Key points to hit:**
- High level:
  - FastAPI backend (`app/main.py` + `app/routes/chat.py`).
  - LangChain‑based LLM utilities (`utils/helper.py`).
  - Pydantic models (`models/chat_models.py`).
  - Streamlit UI (`ui.py`) or any other HTTP client.
- Flow:
  1. Client sends `POST /api/v1/ask/stream` with question + history + expert labels.
  2. Backend initializes local Ollama LLM.
  3. Router chain chooses which expert should answer.
  4. Expert chain streams tokens via `StreamingResponse`.
  5. Client renders streamed text in real time.

#### 7.2 “How does the expert routing work?”

- Using the LLM as a **router**:
  - Input: list of expert labels and the user’s question.
  - Prompt enforces: choose **one** label and output **only** that label.
  - That chosen label is then used to pick the expert‑specific chain.

- You can discuss:
  - Pros:
    - Very flexible (change experts just by changing prompt/labels).
    - No custom training required.
  - Cons:
    - Routing quality depends on prompt and base model; it’s probabilistic.

#### 7.3 “Why did you choose streaming responses instead of a single response?”

- **User experience**:
  - Lower perceived latency; user sees text appearing immediately.
- **Technical control**:
  - Ability to cancel streaming requests early on the client.
  - Potential to interleave UI updates or handle multi‑expert scenarios.
- **Implementation detail you understand**:
  - FastAPI `StreamingResponse` with a Python generator.
  - LangChain’s `chain.stream(...)` to get partial outputs.

#### 7.4 “How would you scale or productionize this?”

Ideas you can mention:

- **Infrastructure**
  - Run behind a production ASGI server setup (e.g. `uvicorn` + `gunicorn` or similar).
  - Containerize the service with Docker (you already have an example Dockerfile in the README).

- **Configuration & Secrets**
  - Move all hard‑coded keys and file paths into environment variables or a secrets manager.
  - Use `.env` files with `python-dotenv` for local dev.

- **Performance**
  - Cache or reuse LLM clients (already partially done).
  - Consider **smaller models** or **distilled models** for routing vs answering.
  - Add request timeouts and rate limiting.

- **Observability**
  - Centralized logging of questions, chosen experts, latency.
  - Metrics on routing accuracy or fallback behavior.

#### 7.5 “How does the RAG / BYOD part work?”

Points you can hit:

- **Ingestion path**
  - Users upload documents through `/api/v1/ask/byod`.
  - The backend:
    - Extracts text (PDF/DOCX/TXT).
    - Chunks into overlapping segments.
    - Embeds each chunk with a local embedding model via Ollama.
    - Stores embeddings + metadata in FAISS on disk.
- **Retrieval path**
  - At question time (`/api/v1/ask/byod-chat`):
    - The question is embedded with the same embedding model.
    - FAISS is queried for nearest neighbors (top‑k chunks).
    - Those chunks are put into the prompt as “document context” before asking the LLM to answer.
- **Why this is useful**
  - Keeps sensitive documents local (no cloud vector DB required).
  - Makes answers traceable to specific chunks and files.
  - Allows you to scale to many documents while keeping latency low.

You can position this as “I built a **local RAG system** using FAISS and Ollama, on top of my existing expert‑routing chat backend.”

#### 7.6 “How does voice input work?”

- **Endpoint**: `POST /api/v1/ask/voice-query` with multipart form: `audio` file + `meta` (JSON with history and expert labels).
- **Pipeline**: Uploaded audio is converted to WAV (using `pydub`) so Whisper can process it. The backend uses the same **Whisper small** model (lazy-loaded in `utils/helper.py`) to transcribe. The transcript becomes the “question” fed into the existing router and expert chain; the response is streamed in the same JSON-lines format as `/stream`, with an initial `transcript` event so the UI can show the recognized text.
- **Interview angle**: You can explain end-to-end multimodal input (audio → text → LLM → streamed text) and reuse of the same routing and streaming logic for both text and voice.

#### 7.7 “What would you improve if you had more time?”

You can pick several:

- Add **tests** (unit + integration) for:
  - Routing logic (e.g. known questions → expected experts).
  - Streaming endpoint behavior.
- Improve **error handling** and **fallbacks** (e.g. if Ollama is down).
- Support **multiple experts in parallel** instead of one at a time.
- Add **authentication** and **rate limiting** for a production deployment.
- Improve the client parsing of streamed JSON so the UI shows only the `content` field instead of raw JSON lines.
- Refine the RAG layer:
  - Switch from a single global index to per‑user namespaces.
  - Add better chunking (e.g. token-aware, semantic splits) and possibly reranking.

---

### 8. How to Present This Project in 2–3 Minutes

You can roughly follow this structure in an interview:

1. **Problem & idea (20–30 seconds)**
   - “I wanted to build a system where different domain experts answer questions, and a router chooses who should answer each question.”
2. **Architecture (45–60 seconds)**
   - Explain FastAPI backend, LangChain + Ollama, Pydantic models, and streaming.
3. **Deeper dive (60–90 seconds)**
   - Talk about:
     - Router prompt design.
     - How expert chains are built and how history is formatted.
     - Streaming implementation (LangChain stream → FastAPI → client).
4. **Extensions (30–45 seconds)**
   - Mention Streamlit UI, speech‑to‑text, text‑to‑speech, and future improvements (tests, routing quality, scaling).

If you’re short on time, focus on: **routing concept + streaming implementation + why that’s valuable**.

---

### 9. Quick Reference Summary (Cheat Sheet)

- **Core idea**: Multi‑expert chat with LLM router, streaming responses; optional voice input and BYOD RAG.
- **Backend**: FastAPI + LangChain + Ollama; `app/main.py`, `app/routes/chat.py`, `utils/helper.py`, `models/chat_models.py`, `utils/rag.py`.
- **Endpoints**: `/ask/` (health), `/ask/stream` (text chat), `/ask/voice-query` (audio → Whisper → same router/expert stream), `/ask/byod` (ingest docs), `/ask/byod-chat` (RAG over ingested docs).
- **Routing**: `router_expert` builds a prompt that forces the LLM to return a **single expert name**.
- **Streaming**: `stream_llm_response` (LangChain stream) → generator → `StreamingResponse` → client.
- **Voice**: Audio → pydub (WAV) → Whisper (small) → transcript as question → same flow as `/stream`; first stream line is `transcript` event.
- **Client**: Streamlit (`ui.py`) calls `/api/v1/ask/stream` and renders the stream; could be swapped for a React frontend.
- **Extras**: BYOD RAG (FAISS + Ollama embeddings), STT/TTS demos and richer Streamlit prototype in `chat_llm.py`.

Use this document as a mental map: for any interview question, try to anchor your answer to one of these sections and file names.

