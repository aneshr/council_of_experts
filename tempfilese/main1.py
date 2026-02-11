import streamlit as st
import time
import random
import os
from fastapi.middleware.cors import CORSMiddleware
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173"], allow_methods=["*"], allow_headers=["*"])
os.environ["GOOGLE_API_KEY"] = ""


st.title('Chat Bot')
'''
st.chat_message(arg1,arg2,,)
arg1 - name of the message author (user,assistant) are the basic ones.
'''
#with st.chat_message("user"):
#    prompt = st.chat_input("Say Somethging....")
#    st.write(prompt)
def response_generator():
    response = random.choice(
        [
            "Hello there! How can I assist you today?",
            "Hi, human! Is there anything I can help you with?",
            "Do you need help?",
        ]
    )
    for word in response.split():
        yield word + " "
        time.sleep(0.05)

# checking if there is messages available in session else initialise
if "messages" not in st.session_state:
    st.session_state.messages = []


## This is displaying the history in the UI.
# With each load this piece of code displays all User and Assistant conversation based on the session object messages
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
st.markdown(st.session_state.messages)
# := this lets us assign values as a part of expression, its called walrus operator.
# It lets you assign value while also checking condition
#### EXAMPLE ####
#while (line := input("> ")) != "quit":
#    print(line)


if prompt := st.chat_input("what is up ??"):
    # since we have a chat history displayed, after that
    # we are just taking the prompt and displaying it here
    with st.chat_message("user"):
        st.markdown(prompt)

    # Updating the session variable
    st.session_state.messages.append({"role":"user","content":prompt})

    # For the question asked by user, displaying assistant response
    with st.chat_message("assistant"):
        response = st.write_stream(response_generator())

    # Updating session with assistant Response
    st.session_state.messages.append({"role":"assistant","content":response})