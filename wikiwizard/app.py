import os
from dotenv import load_dotenv
import streamlit as st
from PIL import Image
import google.generativeai as genai
from gtts import gTTS
import base64
import speech_recognition as sr
from googletrans import Translator

# Load environment variables from .env file
load_dotenv()

# Configure Google Generative AI
api_key = os.getenv("GOOGLE_API_KEY")
if not api_key:
    st.error("Please set the GOOGLE_API_KEY environment variable.")
else:
    genai.configure(api_key=api_key)

# Initialize the Gemini Pro models
text_model = genai.GenerativeModel('gemini-pro')
vision_model = genai.GenerativeModel('gemini-pro-vision')
chat = text_model.start_chat(history=[])

# Initialize Translator
translator = Translator()

# Function to translate text
def translate_text(text, src_language, target_language='en'):
    try:
        translation = translator.translate(text, src=src_language, dest=target_language)
        return translation.text
    except Exception as e:
        st.error(f"Translation error: {e}")
        return text

# Function to detect the language of the text
def detect_language(text):
    try:
        detected_lang = translator.detect(text).lang
        return detected_lang
    except Exception as e:
        st.error(f"Language detection error: {e}")
        return 'en'

# Function to get response for text queries
def get_text_response(question, target_language='en'):
    try:
        detected_lang = detect_language(question)
        translated_question = translate_text(question, src_language=detected_lang, target_language='en')
        response = chat.send_message(translated_question, stream=True)
        response_text = ''.join(chunk.text for chunk in response if chunk.text)
        translated_response = translate_text(response_text, src_language='en', target_language=target_language)
        return translated_response
    except Exception as e:
        st.error(f"An error occurred: {e}")
        return None

# Function to get response for text + image queries
def get_vision_response(input_text, image, target_language='en'):
    try:
        detected_lang = detect_language(input_text)
        translated_text = translate_text(input_text, src_language=detected_lang, target_language='en')
        if translated_text:
            response = vision_model.generate_content([translated_text, image])
        else:
            response = vision_model.generate_content(image)
        if response.text.strip():  # Check if response text is not empty
            translated_response = translate_text(response.text, src_language='en', target_language=target_language)
            return translated_response
        else:
            st.warning("Response did not contain valid text data.")
            return None
    except Exception as e:
        st.error(f"An error occurred: {e}")
        return None

# Function to generate voice output
def generate_voice(text, language='en'):
    tts = gTTS(text, lang=language_code(language))
    tts.save("response.mp3")
    with open("response.mp3", "rb") as audio_file:
        audio_bytes = audio_file.read()
        audio_base64 = base64.b64encode(audio_bytes).decode("utf-8")
    return audio_base64

# Function to get language code from language name
def language_code(language_name):
    language_codes = {
        "English": "en",
        "Spanish": "es",
        "French": "fr",
        "Hindi": "hi",
        "Telugu": "te",
        "Chinese (Simplified)": "zh-CN",
        "Arabic": "ar",
        "Bengali": "bn",
        "Russian": "ru",
        "Portuguese": "pt",
        "Japanese": "ja",
        # Add more languages as needed
    }
    return language_codes.get(language_name, "en")

# Initialize Streamlit app
st.set_page_config(page_title="Wikiwizard")

st.header("Wikiwizard")

# Initialize session state for chat history if it doesn't exist
if 'chat_history' not in st.session_state:
    st.session_state['chat_history'] = []

# Input fields
input_text = st.text_input("Input Prompt: ", key="input_text")
use_webcam = st.checkbox("Use Webcam")

if use_webcam:
    webcam_image = st.camera_input("Take a picture")
    if webcam_image is not None:
        image = Image.open(webcam_image)
else:
    uploaded_file = st.file_uploader("Choose an image...", type=["jpg", "jpeg", "png"])
    if uploaded_file is not None:
        image = Image.open(uploaded_file)
    else:
        image = None

# Language selection
language = st.selectbox("Select Language", ["English", "Spanish", "French", "Hindi", "Telugu", "Chinese (Simplified)", "Arabic", "Bengali", "Russian", "Portuguese", "Japanese"])

# Voice input section
recognizer = sr.Recognizer()
voice_input = None
if st.button("Speak"):
    with sr.Microphone() as source:
        st.write("Listening...")
        audio = recognizer.listen(source)
        try:
            voice_input = recognizer.recognize_google(audio)
            st.write(f"Recognized: {voice_input}")
        except sr.UnknownValueError:
            st.error("Google Speech Recognition could not understand the audio")
        except sr.RequestError as e:
            st.error(f"Could not request results from Google Speech Recognition service; {e}")

# Submit button
submit = st.button("Ask the question")
generate_voice_output = st.checkbox("Generate Voice Output")

# Handle submission
if submit or voice_input:
    response_text = ""
    query = voice_input if voice_input else input_text

    if image:
        # Handle text + image query
        response = get_vision_response(query, image, target_language=language_code(language))
        if response:
            st.subheader("The Response is")
            if isinstance(response, str):
                st.write(response)
                response_text = response
                st.session_state['chat_history'].append(("You", query))
                st.session_state['chat_history'].append(("Bot", response))
            else:
                st.error("Response did not contain valid text data.")
                if hasattr(response, 'candidate') and hasattr(response.candidate, 'safety_ratings'):
                    st.write(f"Safety ratings: {response.candidate.safety_ratings}")
                else:
                    st.write("Response was blocked or invalid.")
    else:
        # Handle text-only query
        response = get_text_response(query, target_language=language_code(language))
        if response:
            st.subheader("The Response is")
            st.write(response)
            response_text = response
            st.session_state['chat_history'].append(("You", query))
            st.session_state['chat_history'].append(("Bot", response))
    
    if generate_voice_output and response_text:
        audio_base64 = generate_voice(response_text, language_code(language))
        audio_html = f'<audio controls autoplay><source src="data:audio/mp3;base64,{audio_base64}" type="audio/mp3"></audio>'
        st.markdown(audio_html, unsafe_allow_html=True)

# Display chat history
st.subheader("The Chat History is")
for role, text in st.session_state['chat_history']:
    st.write(f"{role}: {text}")
