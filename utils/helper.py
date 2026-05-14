"""
Utility helpers used by the FastAPI backend.

Responsibilities of this module:
- Initialize the LLM client (Ollama in this case).
- Format chat history into a single string for prompts.
- Build expert-specific prompt chains.
- Stream responses from the LLM token by token.
"""

import base64
import time
import time  # duplicate import is harmless; kept to avoid non‑comment refactors
import random
import os
import whisper
import tempfile
from typing import Optional

import requests
from langchain_community.chat_models import ChatOllama
from langchain_core.prompts.prompt import PromptTemplate
from pydub import AudioSegment


# Lazy‑initialized global Whisper model so it is loaded only once
_WHISPER_MODEL = None

# Ollama configuration for both text and vision models.
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
VISION_MODEL_NAME = os.getenv("VISION_MODEL_NAME", "llava:7b")


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

def initialize_whisper():
    """
    Initialize and return the small Whisper ASR model.

    The model is cached at module level so it is loaded only once, which
    significantly improves performance for repeated voice queries.
    """
    global _WHISPER_MODEL
    if _WHISPER_MODEL is None:
        _WHISPER_MODEL = whisper.load_model("small")
    return _WHISPER_MODEL


def run_llava_on_image(
    image_bytes: bytes,
    user_question: Optional[str] = None,
    mode: str = "general",
) -> str:
    """
    Call a local LLaVA model (via Ollama) on raw image bytes and return
    a textual summary/analysis.

    Parameters
    ----------
    image_bytes : bytes
        Raw bytes of the uploaded image.
    user_question : str | None
        Optional natural-language question from the user about the image.
    mode : str
        Optional hint to steer the prompt, e.g. "general", "ocr", "diagram".
    """
    if not image_bytes:
        raise ValueError("Uploaded image is empty.")

    prompt_parts = []
    if mode == "ocr":
        prompt_parts.append(
            "You are an OCR assistant. Extract all readable text from this image. "
            "Preserve line breaks where possible."
        )
    elif mode == "diagram":
        prompt_parts.append(
            "You are a diagram analysis assistant. Describe the structure, key "
            "components, and relationships shown in this image."
        )
    else:
        prompt_parts.append(
            "You are a vision assistant. Describe this image in detail, including "
            "any visible text or UI elements."
        )

    if user_question:
        prompt_parts.append(
            f"The user asked: {user_question}\n"
            "Answer their question using only information you can infer from the image."
        )

    prompt = "\n\n".join(prompt_parts)

    # Ollama expects base64-encoded image data for vision models.
    image_b64 = base64.b64encode(image_bytes).decode("utf-8")

    payload = {
        "model": VISION_MODEL_NAME,
        "prompt": prompt,
        "images": [image_b64],
        "stream": False,
    }

    try:
        resp = requests.post(
            f"{OLLAMA_BASE_URL}/api/generate",
            json=payload,
            timeout=60,
        )
        resp.raise_for_status()
    except requests.RequestException as e:
        # Surface a concise error; routes can translate this into HTTPException.
        raise RuntimeError(f"LLaVA request failed: {e}") from e

    data = resp.json()
    # Non-streaming /api/generate responses include the full text in `response`.
    text = data.get("response") or ""
    if not text:
        raise RuntimeError("Empty response from LLaVA vision model.")

    return text.strip()


def convert_to_wav(audio_bytes: bytes) -> str:
    """
    Convert raw audio bytes to a temporary `.wav` file and return its path.

    This helper:
    - Writes the incoming bytes to a temp file.
    - Uses `pydub` to decode and re‑encode as proper WAV.
    - Returns the filesystem path to the WAV file.
    """
    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
        tmp.write(audio_bytes)
        temp_path = tmp.name#get the path of the temp file

    audio = AudioSegment.from_file(temp_path) #convert the audio to wav format
    audio.export(temp_path, format="wav")#export the audio to the temp file
    return temp_path

def format_chat_history(history):
    """
    Format chat history into a readable string (robust version).

    # This function is written to handle various input types safely:
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

def router_expert(llm, expert_list, question):
    """
    Build a routing chain that selects the best expert for a given question.

    The chain, when invoked, should return ONLY the name of the chosen expert.
    """
    # Format expert list once and keep the user question as a template variable
    # so that arbitrary characters (including braces) in the question do not
    # break the PromptTemplate validation.
    expert_block = "\n".join(str(e) for e in expert_list)

    promptT = PromptTemplate(
        input_variables=["question"],
        partial_variables={"expert_list": expert_block},
        template=(
            "You are an expert router.\n\n"
            "Your task is to choose the SINGLE most relevant expert to answer "
            "the user’s question.\n\n"
            "Available experts:\n"
            "{expert_list}\n\n"
            "Rules:\n"
            "- Choose exactly ONE expert.\n"
            "- Return ONLY the expert name.\n"
            "- Do NOT explain your choice.\n"
            "- Do NOT add punctuation or extra words.\n"
            "- If the question spans multiple domains, choose the PRIMARY one.\n"
            "- If uncertain, choose \"None\" as the expert and say that you are "
            "not sure and ask the user to rephrase the question.\n\n"
            "User question:\n"
            "{question}"
        ),
    )

    chain = promptT | llm

    return chain


def chat_expert(llm, expertise, question, chat_history):
    """
    Create a chain that answers as a given expert.

    Parameters
    ----------
    llm : LangChain LLM instance
    expertise : str
        Human-readable domain name (e.g. "Science", "Maths").
    question : str
        Current user question (used when building the chain; passed again at stream time).
    chat_history : list
        Prior conversation messages (formatted inside stream_llm_response).

    Returns
    -------
    chain
        LangChain runnable (PromptTemplate | llm) that expects `chat_history` and `question`.
    """
    promptT = PromptTemplate(
        input_variables=["chat_history", "question"],
        template=(
            f"You are an expert in {expertise}.\n"
            "Here is the conversation so far:\n"
            "{chat_history}\n\n"
            "User: {question}\n"
            "Answer the user's question directly.\n"
        ),
    )
    return promptT | llm


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
    if whisper is None:
        raise ModuleNotFoundError(
            "Whisper is required. Install with: pip install openai-whisper"
        )
    model = whisper.load_model("base")
    return model
