# RAG (Retrieval Augmented Generation) — A General Guide

This document explains how **RAG** works in general: the idea, the pipeline, and the main components. It is not specific to any single project.

---

## 1. What is RAG?

**RAG** stands for **Retrieval Augmented Generation**. It is a pattern where:

1. You have a **body of documents** (your “knowledge base”).
2. When a **user asks a question**, you **retrieve** the most relevant pieces of that knowledge.
3. You **pass those pieces as context** to an **LLM** (Large Language Model), which **generates** an answer grounded in that context.

So: **Retrieval** (find relevant text) + **Augmented** (add it to the prompt) + **Generation** (LLM produces the answer).

---

## 2. Why RAG?

LLMs have limitations that RAG helps address:

| Problem | How RAG helps |
|--------|----------------|
| **Knowledge cutoff** | The model doesn’t know recent or private data. RAG injects that data at query time. |
| **Hallucination** | The model may invent facts. RAG grounds the answer in retrieved passages. |
| **No internal “memory” of your docs** | The model wasn’t trained on your PDFs/docs. RAG makes your docs available as context. |
| **Cost and latency of fine-tuning** | Instead of fine-tuning on your data, you keep the model fixed and retrieve relevant text per query. |

RAG lets you **use your own documents** to improve answers **without retraining** the model.

---

## 3. The Two Phases of RAG

RAG has two main phases:

### 3.1 Indexing (Ingestion) — “Offline” / When Documents Are Added

This runs when you add or update documents, not necessarily when the user asks a question.

```
Documents (PDF, TXT, etc.)
    → Extract text
    → Split into chunks
    → Convert chunks to vectors (embeddings)
    → Store vectors (and text) in a searchable index
```

After this, the system can quickly find chunks that are **semantically similar** to a query.

### 3.2 Query (Retrieval + Generation) — When the User Asks Something

This runs at request time.

```
User question
    → Convert question to a vector (same embedding model)
    → Search the index for the most similar chunks (retrieval)
    → Build a prompt: "Context: [retrieved chunks]. Question: [user question]"
    → Send prompt to LLM
    → Return the LLM’s answer
```

So: **index once**, **retrieve + generate** on every question.

---

## 4. Core Components in Detail

### 4.1 Document Loading & Text Extraction

- **Input**: Raw files (PDF, DOCX, TXT, Markdown, HTML, etc.).
- **Goal**: Get plain text out of each file.
- **Reality**: Format-specific (PDFs need a PDF parser, DOCX need a Word parser, etc.). Tables and images often need extra handling (OCR, layout models).

Your project does this in `utils/rag.py` with extractors per file type (e.g. PDF via PyPDF2, DOCX via python-docx).

---

### 4.2 Chunking (Splitting Text)

- **Why**: LLMs have limited context windows. You can’t feed entire books. You also want small, focused pieces so retrieval is precise.
- **What**: Split long text into **chunks** (e.g. 500–2000 characters or 1–3 paragraphs).
- **Common strategies**:
  - **Fixed size**: e.g. 512 tokens or 1500 characters, with optional **overlap** (e.g. 100–300 characters) so context isn’t lost at boundaries.
  - **Semantic**: Split on paragraphs, sections, or sentences.
  - **Recursive**: Split by separators (e.g. `\n\n`, then `\n`, then space) until chunks are under a target size.

Chunk size and overlap are tunable: larger chunks = more context per chunk but fewer, coarser chunks; smaller = finer-grained but more fragments.

---

### 4.3 Embeddings (Turning Text into Vectors)

- **What**: An **embedding model** maps a piece of text to a **vector** (list of numbers) of fixed length (e.g. 768 or 1536 dimensions).
- **Property**: Semantically similar texts get vectors that are **close** in distance (e.g. cosine similarity or Euclidean distance). So “How do I reset my password?” and “Password reset steps” should be near each other.
- **Who does it**: A separate model from the LLM (e.g. OpenAI `text-embedding-ada-002`, open-source like `nomic-embed-text`, `sentence-transformers`, etc.). Your project uses **Ollama** with an embedding model (e.g. `nomic-embed-text`).
- **Where it’s used**:
  - **Indexing**: Each chunk is embedded and the vector is stored.
  - **Query**: The user question is embedded with the **same model**; that vector is used to search for nearby chunk vectors.

So: **same embedding model** for both chunks and queries, so distances are comparable.

---

### 4.4 Vector Store (The “Index”)

- **What**: A store that holds **vectors** (and usually the original text + metadata) and supports **similarity search**: “given a query vector, return the k nearest vectors.”
- **Examples**: FAISS, Chroma, Pinecone, Weaviate, Qdrant, pgvector, etc.
- **Flow**:
  - **Ingestion**: For each chunk, compute embedding → add vector + document to the store.
  - **Query**: Compute query embedding → run k-NN (e.g. top-5) → get back the best-matching chunks (and their text/metadata).

So the “index” is the structure that makes **similarity search over vectors** fast. “Creating an index” = building this structure (e.g. from the first batch of chunks); “adding documents” = embedding new chunks and inserting their vectors (and docs) into that same structure.

---

### 4.5 Retrieval

- **Input**: User question (as text).
- **Steps**: Embed question → search vector store for top-**k** most similar chunks (e.g. k=5).
- **Output**: A list of **documents** (chunks + metadata) that will form the “context” in the prompt.
- **Improvements** (optional):
  - **Reranking**: Use a separate model to score/rerank the top-N candidates and keep the best k.
  - **Hybrid search**: Combine vector similarity with keyword (BM25) or filter-based search.
  - **Metadata filters**: e.g. only search in “policy” docs or a certain date range.

In the simplest RAG, retrieval = one vector similarity search and take top-k.

---

### 4.6 Generation

- **Input**: The user question + the retrieved chunks (as context).
- **Prompt shape**: Something like:  
  `“Use the following context to answer the question. Context: … Question: …”`
- **Process**: Send that prompt to an LLM (e.g. via OpenAI API, or local model via Ollama). The LLM generates an answer.
- **Output**: The model’s reply (and optionally citations to the retrieved chunks).

So **generation** is “LLM reads context + question and produces the final answer.” RAG’s value is that the context is **retrieved** from your docs, not from the model’s training.

---

## 5. End-to-End Flow (Summary)

```
[Indexing]
  Documents → Extract text → Chunk → Embed chunks → Store in vector index

[Query]
  User question → Embed question → Retrieve top-k chunks → Build prompt (context + question)
    → LLM generates answer → Return answer (and optionally sources)
```

The **index** is the vector store (e.g. FAISS) that was built from chunk embeddings. **Creating** the index = building it from the first set of chunks; **adding documents** = embedding new chunks and inserting them into that index. Both creation and add use the same embedding model so that later, the query embedding is in the same “space” and similarity search is meaningful.

---

## 6. Variations and Enhancements

| Idea | Description |
|------|-------------|
| **Simple RAG** | One embedding model, one vector store, top-k retrieval, single LLM call. |
| **Hybrid search** | Combine vector similarity + keyword (BM25) and merge or rerank results. |
| **Reranking** | Retrieve more (e.g. 20), then use a reranker model to pick the best 5. |
| **Multi-query / HyDE** | Rephrase the question or generate hypothetical answers, embed those too, and retrieve with multiple vectors. |
| **Chunk filtering** | Use metadata (source, date, type) to restrict which chunks are searchable. |
| **Citation / source tracing** | Attach chunk IDs or doc names to the prompt so the LLM can cite sources; or return chunks with the answer. |

---

## 7. Trade-offs and Best Practices

- **Chunk size**: Larger = more context per chunk but less precise retrieval; smaller = more precise but may lose narrative flow. Overlap can help at boundaries.
- **k (number of chunks)**: Too small → missing relevant info; too large → noise and context-window waste. Often 3–10 is a good range to tune.
- **Embedding model**: Must be the same for indexing and querying. Match the model to your language and domain if possible.
- **Vector store choice**: Depends on scale (in-memory FAISS vs distributed Pinecone), persistence, and filters. Your project uses FAISS persisted to disk for simplicity and local use.
- **Prompt design**: Clear instructions (“answer only from the context”, “if unsure say so”) reduce hallucination and off-topic answers.

---

## 8. How This Project Uses RAG (Quick Map)

In this codebase:

- **Indexing**: `utils/rag.py` — `ingest_document()` extracts text, chunks with `_chunk_text()`, embeds with Ollama (`nomic-embed-text`), and stores/updates a FAISS index in `rag_store/faiss`.
- **Query**: `retrieve_context()` loads the FAISS index, embeds the question, runs `similarity_search(question, k=5)`, and returns the top chunks. The chat/route layer then builds the prompt with that context and calls the LLM.

So the same general RAG pipeline (documents → chunks → embeddings → vector index; question → embed → retrieve → prompt → LLM) is implemented here with local Ollama for both embeddings and (typically) the generator.

---

## 9. Further Reading

- [LangChain RAG tutorial](https://python.langchain.com/docs/tutorials/rag/)
- [LlamaIndex documentation](https://docs.llamaindex.ai/) (another RAG/orchestration framework)
- Papers: “Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks” (Lewis et al., 2020)
