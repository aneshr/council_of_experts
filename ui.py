import streamlit as st
import os
import tempfile
import base64
import requests
st.set_page_config(page_title="Experts Council", layout="centered")

st.title("💬 AI Chat with Experts")

# Maintain chat history
if "messages" not in st.session_state:
    st.session_state.messages = []

if "page" not in st.session_state:
    st.session_state.page = "welcome"

if "e1" not in st.session_state:
    st.session_state.e1 = None

if "e2" not in st.session_state:
    st.session_state.e2 = None

if "e3" not in st.session_state:
    st.session_state.e3 = None

def go_to_chat(e1,e2,e3):
    st.session_state.expert = [e1,e2,e3]
    st.session_state.page = "chat"
    st.rerun()

if st.session_state.page == "welcome":
    st.markdown("## 👋 Welcome to the AI Expert Assistant")

    expert_1 = user_text = st.text_input("Expert 1", value = "Science")
    expert_2 = user_text = st.text_input("Expert 2", value = None)
    expert_3 = user_text = st.text_input("Expert 3", value = None)

    if st.button("Continue ➜"):
        go_to_chat(expert_1,expert_2,expert_3)

elif st.session_state.page == "chat":
    exp_l = [e for e in st.session_state.expert if e is not None]
    st.markdown(f"### 💬 Chatting with **{', '.join(exp_l)} Expert(s)**")

    chat_area = st.container()
    with chat_area:
        for msg in st.session_state.messages:
            align = "right" if msg["role"] == "user" else "left"
            bg = "#0078ff" if msg["role"] == "user" else "#e5e5e5"
            color = "#fff" if msg["role"] == "user" else "#000"
            st.markdown(
                f"""
                <div style='text-align:{align};
                            background:{bg};
                            color:{color};
                            padding:8px;
                            border-radius:10px;
                            margin:5px;
                            max-width:80%;
                            display:inline-block;'>
                    {msg["content"]}
                </div>
                """,
                unsafe_allow_html=True
            )
        # Placeholder for streaming response
        placeholder = st.empty()
    if st.button("⬅️ Back"):
        st.session_state.page = "welcome"
        st.rerun()
    st.markdown("---")
    col_input, col_send = st.columns([5, 1])

    with col_input:
        user_input = st.text_input("Type your message:", key="user_input")

    with col_send:
        send = st.button("Send", use_container_width=True)

    if send and user_input:
        # Add user's message to history
        st.session_state.messages.append({"role": "user", "content": user_input})

        
        full_response = ""

        # Send question to FastAPI
        response = requests.post(
            "http://127.0.0.1:8000/api/v1/ask/stream",
            json={"question": user_input,
            "history": st.session_state.messages,
            "expert1": st.session_state.expert[0],
            "expert2": st.session_state.expert[1],
            "expert3": st.session_state.expert[2]
            },
            stream=True,
        )

        # Stream tokens from backend
        for chunk in response.iter_content(chunk_size=None):
            if chunk:
                text = chunk.decode("utf-8")
                full_response += text
                placeholder.markdown(
                    f"""
                    <div style='text-align:left;
                                background:#e5e5e5;
                                color:black;
                                padding:8px;
                                border-radius:10px;
                                margin:5px;
                                max-width:80%;
                                display:inline-block;'>
                        {full_response}
                    </div>
                    """,
                    unsafe_allow_html=True
                )

        # Add assistant's response to chat history
        st.session_state.messages.append(
            {"role": "assistant", "content": full_response}
        )

        # Clear input and rerun to refresh chat
        st.session_state.user_input = ""
        st.rerun()




