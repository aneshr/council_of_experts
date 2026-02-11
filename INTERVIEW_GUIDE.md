## Chat App – Interview Prep Guide

This document is designed to help you **explain this project in interviews** – from a 30–60 second elevator pitch, to deeper architecture and design questions.

---

### 1. High‑Level Elevator Pitch

- **What this project is**
  - A **FastAPI backend** that powers an **“experts council” chat system**.
  - A user asks a question; an **LLM router** picks the best “expert”; that expert’s LLM chain generates and **streams** the answer token‑by‑token to the client.
  - There are also **Streamlit UIs** and **speech (STT/TTS)** utilities built around the same idea.

- **One‑liner you can say**
  - “I built a FastAPI‑based multi‑expert chat backend that uses an LLM as a router to pick the best expert per question and streams responses in real time to a web UI, with optional speech‑to‑text and text‑to‑speech add‑ons.”

---

### 2. Tech Stack Overview

- **Backend**
  - `FastAPI` for the HTTP API.
  - `uvicorn` as the ASGI server.
  - `Pydantic` models for request validation (`Message`, `ChatRequest`).
  - `LangChain` / `langchain_community` with `ChatOllama` as the LLM client.
  - Local LLM served by **Ollama** (e.g. `gemma2:2b`).

- **Frontend / UI**
  - Primary expectation: can be any HTTP client (e.g. React).
  - Existing **Streamlit UIs**:
    - `ui.py`: simple web chat that calls the FastAPI streaming endpoint.
    - `chat_llm.py`: richer prototype combining experts, summarization, STT, and TTS directly with cloud LLMs.

- **Speech & Audio**
  - `whisper` and `faster_whisper` for speech‑to‑text demos (`speechtotext.py`, `sp-to-txt.py`).
  - `TTS` library for text‑to‑speech demos (`texttospeech.py`, parts of `chat_llm.py`).

---

### 3. Backend Architecture (FastAPI + LLM Router)

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

- **Two main endpoints**
  - `GET /api/v1/ask/`
    - Simple health/test endpoint returning a static JSON message.
  - `POST /api/v1/ask/stream`
    - Main **streaming chat endpoint**.
    - Accepts a `ChatRequest` body with:
      - `question: str`
      - `history: List[Message]`
      - `expert1`, `expert2`, `expert3`: expert labels (e.g. “Science”, “Mathematics”).

- **Flow inside `/stream`**
  1. **Collect experts** from the request into `expert_list`.
  2. **Initialize the LLM** via `initialize_llm()` from `utils.helper`.
  3. **Ask the router** which expert should answer using `get_expert_from_router()`, which:
     - Builds a routing chain via `router_expert(llm, expert_list, question)`.
     - Calls `llm_response(chain, question)` to get back **just the expert name**.
  4. **Build expert chain(s)**:
     - Currently uses `chat_expert_1(llm, chosen_expert, question, history)` to get a LangChain chain.
  5. **Stream response**:
     - Defines a `generate()` Python generator.
     - Iterates over `stream_llm_response(chain, question, history)` for each expert.
     - Yields **newline‑delimited JSON**:
       - `{"expert": "<name>", "content": "<token_chunk>"}` repeated.
       - Ends with `{"expert": "<name>", "event": "end"}`.
  6. Wraps `generate()` in `StreamingResponse` with `media_type="text/plain"`.

- **Talking point (design choice)**
  - Using `StreamingResponse` + a generator lets the client **render tokens as they arrive**, improving perceived latency and UX, especially compared to waiting for a full LLM response.

#### 3.3 Data Models – `models/chat_models.py`

- `Message`
  - Represents a single chat message with:
    - `role: str` – `"user"`, `"assistant"`, or expert name.
    - `content: str` – the text of the message.

- `ChatRequest`
  - Request model for `/api/v1/ask/stream`.
  - Contains:
    - `question: str`
    - `history: Optional[List[Message]] = []`
    - `expert1: Optional[str] = "science"`
    - `expert2: Optional[str] = "None"`
    - `expert3: Optional[str] = "None"`

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
    - “If uncertain, choose the first expert.”
- Composes the prompt with the LLM via `promptT | llm` to create a chain.

**Conceptual explanation for interviews:**
- You treat the LLM as a **classifier / router** that maps:
  - Input: `(question, list_of_experts)`
  - Output: **single expert label**.
- This is a form of **tool routing / mixture‑of‑experts**, implemented purely via prompting rather than custom ML training.

#### 4.5 Expert Chains – `chat_expert_1/2/3`

- Each expert function:
  - Creates a `PromptTemplate` like:
    - `"You are an expert in {expertise}."`
    - Includes formatted `chat_history`.
    - Includes `"User: {question}"`.
  - Pipes the prompt into `llm` to create a chain (`promptT | llm`).
- They are structurally similar but **separated** so each expert’s style or instructions can be customized later.

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

### 5. Frontend & Streaming Client – `ui.py`

`ui.py` is a **Streamlit** client that talks to the FastAPI backend.

- **Page state**
  - Maintains:
    - `st.session_state.messages`: chat history.
    - `st.session_state.page`: `"welcome"` vs `"chat"`.
    - Expert names (`e1`, `e2`, `e3`).

- **Welcome screen**
  - Lets the user pick labels for three experts (e.g. “Science”, “Mathematics”).

- **Chat screen**
  - Renders history with simple left/right bubble styling.
  - On `Send`:
    - Adds user message to `messages`.
    - Sends a `POST` to `http://127.0.0.1:8000/api/v1/ask/stream` with:
      - `question`
      - `history` (the current messages)
      - `expert1/2/3` (chosen expert labels).
    - Consumes the streaming response in a loop:
      - `response.iter_content(chunk_size=None)`.
      - Updates a placeholder to simulate **streaming text** in the UI.
    - Finally appends a combined `"assistant"` message to history.

**Interview angle:**
- You can explain both sides of streaming:
  - **Server**: generator + `StreamingResponse`.
  - **Client**: incremental rendering as chunks arrive.

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

#### 7.5 “What would you improve if you had more time?”

You can pick several:

- Add **tests** (unit + integration) for:
  - Routing logic (e.g. known questions → expected experts).
  - Streaming endpoint behavior.
- Improve **error handling** and **fallbacks** (e.g. if Ollama is down).
- Support **multiple experts in parallel** instead of one at a time.
- Add **authentication** and **rate limiting** for a production deployment.
- Improve the client parsing of streamed JSON so the UI shows only the `content` field instead of raw JSON lines.

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

- **Core idea**: Multi‑expert chat with LLM router, streaming responses.
- **Backend**: FastAPI + LangChain + Ollama; `app/main.py`, `app/routes/chat.py`, `utils/helper.py`, `models/chat_models.py`.
- **Routing**: `router_expert` builds a prompt that forces the LLM to return a **single expert name**.
- **Streaming**: `stream_llm_response` (`LangChain` stream) → generator → `StreamingResponse` → client.
- **Client**: Streamlit (`ui.py`) calls `/api/v1/ask/stream` and renders the stream; could be swapped for a React frontend.
- **Extras**: STT/TTS + richer Streamlit prototype in `chat_llm.py`.

Use this document as a mental map: for any interview question, try to anchor your answer to one of these sections and file names.

