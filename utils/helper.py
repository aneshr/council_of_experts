import time
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

def init_credentials():
    os.environ["GOOGLE_API_KEY"] = ""
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "/Users/aneesh/Work/chat_app/speech.json"

def play_audio_blocking(path: str):
    os.system(f'afplay "{path}"')

def initialize_llm(model_name="gemini-2.0-flash",temperature=0.5):
    llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash",temperature=temperature)
    
    return llm

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
    '''
        chain : 
        question :
        history: 

        Helps to stream LLM response and also returns a full response.
    '''
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


def chat_expert_1(llm,expertise,question,chat_history):
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

    return chain

    response = st.write_stream(stream_llm_response(chain,question,chat_history))
    with st.spinner("Generating Speech..."):
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as f:
            temp_path = f.name
        tts.tts_to_file(text=response, file_path=temp_path)
        st.audio(temp_path)
        play_audio_blocking(temp_path)
    return response

def chat_expert_2(llm,expertise,question,chat_history):
    promptT = PromptTemplate(
    input_variables=["chat_history", "question"],
        template=(
            f"You are an expert in {expertise}.\n"
            "Here is the conversation so far:\n"
            "{chat_history}\n\n"
            f"{expertise} Expert:"
        ))

    chain = promptT | llm
    return chain
    response = st.write_stream(stream_llm_response(chain,question,chat_history))
    
    return response

def chat_expert_3(llm,expertise,question,chat_history):
    promptT = PromptTemplate(
    input_variables=["chat_history", "question"],
        template=(
            f"You are an expert in {expertise}.\n"
            "Here is the conversation so far:\n"
            "{chat_history}\n\n"
            f"{expertise} Expert:"
        ))

    chain = promptT | llm

    return chain

    response = st.write_stream(stream_llm_response(chain,question,chat_history))

    return response

def summarizer(llm,question,chat_history,expert1,expert2,expert3):
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

    response = st.write_stream(stream_llm_response(chain,question,chat_history))

    return response


def initiaize_whisper():
    model = whisper.load_model("base")
    return model
