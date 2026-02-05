"""
Utility helpers used by the FastAPI backend.

Responsibilities of this module:
- Initialize the LLM client (Ollama in this case).
- Format chat history into a single string for prompts.
- Build expert-specific prompt chains.
- Stream responses from the LLM token by token.
"""

import time
import time  # duplicate import is harmless; kept to avoid non‑comment refactors
import random
import os
import whisper
import tempfile
from langchain_community.chat_models import ChatOllama
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain
from langchain_google_genai import ChatGoogleGenerativeAI
from streamlit_mic_recorder import mic_recorder


def play_audio_blocking(path: str):
    """
    Play an audio file synchronously using the system `afplay` command.

    Parameters
    ----------
    path : str
        Path to the audio file that should be played.
    """
    os.system(f'afplay "{path}"')


def initialize_llm(model_name="gemma2:2b"):
    """
    Initialize and return a ChatOllama client that talks to a local Ollama
    server.

    Parameters
    ----------
    model_name : str, optional
        Name of the Ollama model to use, by default "gemma2:2b".
    """
    llm = ChatOllama(
        model=model_name,
        base_url="http://localhost:11434"
    )
    return llm


def format_chat_history(history):
    """
    Format chat history into a readable string (robust version).

    The function is defensive and supports:
    - Pydantic / object-style messages (with `.role` and `.content` attrs).
    - Dict-style messages (with "role" and "content" keys).
    - Skips empty messages.
    """
    lines = []

    for item in history:
        # handle both dicts and objects
        role = getattr(item, "role", None)
        content = getattr(item, "content", None)

        # fallback if it's a dict
        if role is None and isinstance(item, dict):
            role = item.get("role")
            content = item.get("content")

        if not content:
            # ignore messages without content
            continue

        role_lower = role.lower() if role else ""

        if role_lower == "user":
            lines.append(f"User: {content}")
        elif role_lower == "assistant":
            lines.append(f"Assistant: {content}")
        elif role_lower == "system":
            lines.append(f"System: {content}")

    return "\n".join(lines)




def stream_llm_response(chain,question,history):
    """
    Stream LLM response tokens while also collecting the full response.

    Parameters
    ----------
    chain :
        LangChain runnable (PromptTemplate | llm) that supports `.stream`
        and expects `chat_history` and `question` as inputs.
    question : str
        Current user question.
    history : list
        Previous conversation messages to be formatted into `chat_history`.
    """
    response = ""
    for chunk in chain.stream({"chat_history":format_chat_history(history),"question":question}):
        response += chunk.content
        yield chunk.content
        time.sleep(0.05)
        #yield chunk.content
    return response


def llm_response(chain, question):
    """
    Get the full response from the chain at once (non‑streaming helper).
    """
    result = chain.invoke({"question": question})
    
    # Return the complete content (no yield)
    return result.content

def router_expert(llm,expert_list,question):
    """
    Build a routing chain that selects the best expert for a given question.

    The chain, when invoked, should return ONLY the name of the chosen expert.
    """
    promptT = PromptTemplate(
    input_variables=["question"],
        template=(
            f"""
                You are an expert router.

                Your task is to choose the SINGLE most relevant expert to answer the user’s question.

                Available experts:
                {expert_list}

                Rules:
                - Choose exactly ONE expert.
                - Return ONLY the expert name.
                - Do NOT explain your choice.
                - Do NOT add punctuation or extra words.
                - If the question spans multiple domains, choose the PRIMARY one.
                - If uncertain, choose first expert.

                User question:
                {question}
                """
                ))

    chain = promptT | llm

    return chain


def chat_expert_1(llm,expertise,question,chat_history):
    """
    Create a chain that answers as Expert 1.

    `expertise` is a human‑readable domain name (e.g. "Science").
    """
    promptT = PromptTemplate(
    input_variables=["chat_history", "question"],
        template=(
            f"You are an expert in {expertise}.\n"
            "Here is the conversation so far:\n"
            "{chat_history}\n\n"
            "User: {question}\n"
            "Answer the user's question directly.\n"
            
        ))

    chain = promptT | llm

    return chain

    # response = st.write_stream(stream_llm_response(chain,question,chat_history))
    # with st.spinner("Generating Speech..."):
    #     with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as f:
    #         temp_path = f.name
    #     tts.tts_to_file(text=response, file_path=temp_path)
    #     st.audio(temp_path)
    #     play_audio_blocking(temp_path)
    # return response

def chat_expert_2(llm,expertise,question,chat_history):
    """
    Create a chain that answers as Expert 2.

    This is structurally similar to `chat_expert_1`, but separated so you
    can easily customize prompts per expert.
    """
    promptT = PromptTemplate(
    input_variables=["chat_history", "question"],
        template=(
            f"You are an expert in {expertise}.\n"
            "Here is the conversation so far:\n"
            "{chat_history}\n\n"
            "User: {question}\n"
            "Answer the user's question directly.\n"
            
        ))

    chain = promptT | llm
    return chain


def chat_expert_3(llm,expertise,question,chat_history):
    """
    Create a chain that answers as Expert 3.

    Currently mirrors the structure of Expert 1 and 2.
    """
    promptT = PromptTemplate(
    input_variables=["chat_history", "question"],
        template=(
            f"You are an expert in {expertise}.\n"
            "Here is the conversation so far:\n"
            "{chat_history}\n\n"
            "User: {question}\n"
            "Answer the user's question directly.\n"
            
        ))

    chain = promptT | llm

    return chain


def summarizer(llm,question,chat_history,expert1,expert2,expert3):
    """
    Create a summarization chain that:
    - Reads the whole conversation.
    - Mentions what each expert contributed.
    - Produces a concise answer (< 20 words).
    """
    promptT = PromptTemplate(
    input_variables=["chat_history", "question"],
        template=(
            f"You are an expert in summarization of conversations.\n"
            f"Experts are {expert1} Expert, {expert2} Expert, {expert3} Expert\n"
            "Here is the conversation so far, check if any Expert made any points\n"
            "Summarize what each expert said and give a good answer less than 20 words."
            "Don't provide User tags while answering, only provide expert name and what is he explaing concisly."
            "If there is nothing to discuss just greet"
            "{chat_history}\n\n"
            f"Assistant:"
        ))

    chain = promptT | llm
    return chain


def initiaize_whisper():
    """
    Initialize and return the base Whisper ASR model.

    NOTE: function name is intentionally kept as‑is to avoid changing call
    sites; only documentation has been added.
    """
    model = whisper.load_model("base")
    return model
