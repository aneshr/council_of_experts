import streamlit as st
import os
from streamlit_mic_recorder import mic_recorder
import base64
import whisper

os.environ["GOOGLE_API_KEY"] = ""
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "/Users/aneesh/Work/chat_app/speech.json"

# audio_data = mic_recorder(start_prompt="Start Recording", stop_prompt="Stop Recording")
# if audio_data:
#     # Play the recorded audio
#     st.audio(audio_data["bytes"])

#     # Get raw bytes
#     audio_bytes = audio_data["bytes"]

#     # Convert to Base64 string
#     prompt = base64.b64encode(audio_data["bytes"]).decode("utf-8")

#     with open("recorded.wav", "wb") as f:
#             f.write(audio_bytes)


model = whisper.load_model("base")
result = model.transcribe("recorded.wav", fp16=False)

print(result["text"])
