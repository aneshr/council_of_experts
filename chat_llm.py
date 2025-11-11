import streamlit as st
import time
import random
import os
import whisper
import tempfile
from langchain_openai import ChatOpenAI
from google.cloud import speech
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain
from langchain_google_genai import ChatGoogleGenerativeAI
from streamlit_mic_recorder import mic_recorder
import base64

from TTS.api import TTS
os.environ["GOOGLE_API_KEY"] = ""
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "/Users/aneesh/Work/chat_app/speech.json"
if "temperature" not in st.session_state:
    st.session_state.temperature = 0.5
if "disable" not in st.session_state:
    st.session_state.disable = False

def play_audio_blocking(path: str):
    os.system(f'afplay "{path}"')

@st.cache_resource
def load_tts_model():
    return TTS(model_name="tts_models/en/ljspeech/tacotron2-DDC", progress_bar=False, gpu=False)
tts = load_tts_model()


def format_chat_history(history):
    """Format history list into a readable string"""
    #return "\n".join([f"User: {u}\nAssistant: {a}" for u, a in history])
    history_string = ""
    user = True
    for item in history:
        if user:
            history_string += f"User: {item['content']}\n"
            user = False
        else:
            history_string += f"Assistant: {item['content']}\n"
            user = True
    return history_string

def stream_llm_response(chain,question,history):
    response = ""
    for chunk in chain.stream({"chat_history":history,"question":question}):
        response += chunk.content
        yield chunk.content
        time.sleep(0.05)
        #yield chunk.content
    return response


def llm_response(chain, question, history):
    # Get the full response from the chain at once
    result = chain.invoke({"chat_history": history, "question": question})
    
    # Return the complete content (no yield)
    return result.content

st.title('Chat Bot')

llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash",temperature=st.session_state.temperature)

def summarize_help(chain,history):
    promptT = PromptTemplate(
    input_variables=["chat_history"],
    template=(
        "You are a helpful assistant.\n"
        "Here is the conversation so far:\n"
        "{chat_history}\n\n"
        "Summarize the who history and provide a useful summarization\n"
        "Assistant:"
    ))
    chain = promptT | llm

    response = ""
    for chunk in chain.stream({"chat_history":history}):
        response += chunk.content
        yield chunk.content
        time.sleep(0.05)
        #yield chunk.content
    return response

def summarize_text():
    st.session_state.messages.append({"role":"user","content":"Summarize the text based on the history"})
    # For the question asked by user, displaying assistant response
    
    response = st.write_stream(summarize_help(chain,chat_history))
    # Updating session with assistant Response
    st.session_state.messages.append({"role":"assistant","content":response})

audio_data = prompt = None
with st.sidebar:
    st.session_state.temperature = st.slider("Temperature", float(0),float(1),0.5)
    st.button("Summarize...",on_click=summarize_text)
    audio_data = mic_recorder(start_prompt="Start Recording", stop_prompt="Stop Recording")
    expert1 = st.text_input("Expert 1",value="Science")
    expert2 = st.text_input("Expert 2",value="Mathematics")
    expert3 = st.text_input("Expert 3",value="Psycology")

print(f"{expert1} {expert2} {expert3}")

prompt = st.chat_input("what is up ??")
if prompt:
    audio_data = None

# checking if there is messages available in session else initialise
if "messages" not in st.session_state:
    st.session_state.messages = []



def chat_expert_1(expertise,question,chat_history):
    promptT = PromptTemplate(
    input_variables=["chat_history", "question"],
        template=(
            f"You are an expert in {expertise}.\n"
            "Here is the conversation so far, check if any other Expert made any points else you are the first expert to answer:\n"
            "{chat_history}\n\n"
            "User: {question}\n"
            f"{expertise} Expert:"
        ))

    chain = promptT | llm

    response = st.write_stream(stream_llm_response(chain,question,chat_history))
    with st.spinner("Generating Speech..."):
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as f:
            temp_path = f.name
        tts.tts_to_file(text=response, file_path=temp_path)
        st.audio(temp_path)
        play_audio_blocking(temp_path)
    return response

def chat_expert_2(expertise,question,chat_history):
    promptT = PromptTemplate(
    input_variables=["chat_history", "question"],
        template=(
            f"You are an expert in {expertise}.\n"
            "Here is the conversation so far:\n"
            "{chat_history}\n\n"
            f"{expertise} Expert:"
        ))

    chain = promptT | llm

    response = st.write_stream(stream_llm_response(chain,question,chat_history))
    
    return response

def chat_expert_3(expertise,question,chat_history):
    promptT = PromptTemplate(
    input_variables=["chat_history", "question"],
        template=(
            f"You are an expert in {expertise}.\n"
            "Here is the conversation so far:\n"
            "{chat_history}\n\n"
            f"{expertise} Expert:"
        ))

    chain = promptT | llm

    response = st.write_stream(stream_llm_response(chain,question,chat_history))

    return response

def summarizer(question,chat_history):
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
    response = st.write_stream(stream_llm_response(chain,question,chat_history))

    return response

## This is displaying the history in the UI.
# With each load this piece of code displays all User and Assistant conversation based on the session object messages
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# := this lets us assign values as a part of expression, its called walrus operator.
# It lets you assign value while also checking condition

#prompt = st.chat_input("what is up ??")


model = whisper.load_model("base")
client = speech.SpeechClient()
if audio_data and "bytes" in audio_data and audio_data["bytes"]:
    # Play the recorded audio
    # st.audio(audio_data["bytes"])
    
    # Get raw bytes
    audio_bytes = audio_data["bytes"]
    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
        tmp.write(audio_bytes)
        wav_path = tmp.name
    
    st.success(f"Saved audio file: {wav_path}")
    # # Convert to Base64 string
    # prompt = base64.b64encode(audio_data["bytes"]).decode("utf-8")
    with st.spinner("Transcribbing....."):
        result = model.transcribe(f"{wav_path}", fp16=False)
        prompt = result["text"]
else:
    audio_data = None


if prompt:
    print(prompt)
    print("***********************\n")
    print(st.session_state.messages)
    #st.session_state.disable = True
    # since we have a chat history displayed, after that
    # we are just taking the prompt and displaying it here
    with st.chat_message("user"):
        question = prompt
        st.markdown(question)
    
    # Updating the session variable
    st.session_state.messages.append({"role":"user","content":prompt})
    # print(st.session_state.messages)
    # For the question asked by user, displaying assistant response
    with st.spinner("Thinking....."):
        with st.chat_message(f"{expert1}"):
            chat_history = format_chat_history(history=st.session_state.messages)
            response = chat_expert_1(f"{expert1}",question,chat_history)
            st.session_state.messages.append({"role":f"{expert1}","content":response})
    
    with st.spinner("Thinking....."):
        with st.chat_message(f"{expert2}"):
            chat_history = format_chat_history(history=st.session_state.messages)
            response = chat_expert_2(f"{expert2}",question,chat_history)
            st.session_state.messages.append({"role":f"{expert2}","content":response})
    
    with st.spinner("Thinking....."):
        with st.chat_message(f"{expert3}"):
            chat_history = format_chat_history(history=st.session_state.messages)
            response = chat_expert_3(f"{expert3}",question,chat_history)
            st.session_state.messages.append({"role":f"{expert3}","content":response})
    print(chat_history)
    with st.spinner("Summarizing....."):
        with st.chat_message("assistant"):
            chat_history = format_chat_history(history=st.session_state.messages)
            response = summarizer(question,chat_history)
            # st.session_state.messages.append({"role":f"assistant","content":response})
    # with st.chat_message("assistant"):
    #     response = st.write_stream(stream_llm_response(chain,question,chat_history))
    # st.session_state.disable = False
    # Updating session with assistant Response
    

