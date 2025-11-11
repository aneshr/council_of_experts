CHAT_APP/
├── app/
│   ├── main.py              # FastAPI entry point
│   ├── routes/
│   │   ├── chat.py          # /chat endpoint(s)
│   │   └── health.py
│   ├── core/
│   │   ├── llm_chain.py     # LangChain or LLM setup
│   │   └── config.py
│   └── utils/
│       └── helpers.py
├── streamlit_app/
│   └── main.py              # Streamlit frontend calling FastAPI
├── requirements.txt
└── README.md


Frontend (Streamlit)
   ↓  (HTTP POST)
FastAPI endpoint → validates input
   ↓
calls service function (LLM / Whisper / Expert)
   ↓
gets result (text, stream, etc.)
   ↓
returns JSON or stream response
