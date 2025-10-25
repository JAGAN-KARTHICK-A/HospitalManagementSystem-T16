import speech_recognition as sr
import pyttsx3
import time
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.schema import HumanMessage, SystemMessage, AIMessage
import json
import os
import numpy as np
from faster_whisper import WhisperModel
import requests

os.environ["GOOGLE_API_KEY"] = "AIzaSyA29vrgfMmglSXDp5qaijtS33g0nhByzNw"
MODEL = "small.en"

LOCATION = "Trichy - Samayapuram"

whisper_model = None

chat = ChatGoogleGenerativeAI(
    model = "gemini-2.5-flash",
    temperature = 0.7
)

system_command = """

YOU ARE `SRM VIRTUAL NURSE`. YOU LISTEN TO A IN-PATIENT'S CONTINUOUS VOICE.
YOU ARE IN A VERY CRUCIAL POSITION.

YOU HAVE TO DETECT ANY EMERGENCIES IN THEIR SPEECH AND JUS COMMUNICATE WITH THEM IF NEEDED. IF AN EMERGENCY HAPPENS THEN PROCEED TO REPORT.

IMPORTANT: YOU HAVE TO RESPONSE ONLY IN JSON FORMAT AND NEVER EVER INCLUDE Markdown(MD) CONTENTS IN YOUR RESPONSES.

YOUR RESPONSES:
    - {"rtype":"talk", "content":<content will be spoken to the patient>}
    - {"rtype":"report", "content":<content will be reported>, "level":<emergency level from 1 to 5>}

YOUR INPUT:
    - {"speech":<the recognized speech of the patient live>}

"""
chatHistory = [SystemMessage(content=system_command)]

try:
    tts_engine = pyttsx3.init()
    tts_engine.setProperty('rate', 160)

    recognizer = sr.Recognizer()
    
    recognizer.dynamic_energy_threshold = True
    recognizer.pause_threshold = 1.0

except Exception as e:
    print(f"Error initializing audio engines: {e}")
    print("Please ensure you have a working microphone and speaker.")
    exit()

def speak(text):
    print(f"ASSISTANT: {text}")
    try:
        tts_engine.say(text)
        tts_engine.runAndWait()
    except Exception as e:
        print(f"Error during speech synthesis: {e}")

def listen_for_command():
    global whisper_model
    with sr.Microphone(sample_rate=16000) as source:
        print("\nListening for patient request...")
        
        try:
            audio = recognizer.listen(source, timeout=5, phrase_time_limit=10)
            
            print("Processing audio...")

            text = recognizer.recognize_google(
                audio,
                language="en-US"
            )
            """
            text = recognizer.recognize_whisper(
                audio,
                model=MODEL,
                language="english"
            )
            
            raw_data = audio.get_raw_data(convert_rate=16000, convert_width=2)
            
            # 2. Convert raw bytes to a NumPy array of 16-bit integers
            audio_int16 = np.frombuffer(raw_data, dtype=np.int16)
            
            # 3. Convert 16-bit int to 32-bit float (Whisper standard)
            audio_float32 = audio_int16.astype(np.float32) / 32768.0
            
            # 4. Transcribe using the loaded faster-whisper model
            segments, info = whisper_model.transcribe(
                audio_float32,
                beam_size=5,
                language="en"
            )
            
            # 5. Combine all transcribed segments into one string
            text = "".join(segment.text for segment in segments).strip().lower()"""
            
            text = text.strip().lower()
            print(f"PATIENT: \"{text}\"")
            return text

        except sr.WaitTimeoutError:
            print("Listening timed out. No speech detected.")
            return None
        except sr.UnknownValueError:
            print("Whisper could not understand the audio.")
            return None
        except Exception as e:
            print(f"Error during audio recognition: {e}")
            return None

def process_command(text):
    if not text:
        return True

    chatHistory.append(HumanMessage(content=json.dumps({"speech":text})))
    __resp = chat.invoke(chatHistory).content
    print(__resp)

    __resp = json.loads(__resp)

    if __resp["rtype"] == "talk":
        if len(__resp["content"]) > 0:
            speak(__resp["content"])
    elif __resp["rtype"] == "report":
        print("REPORTING: ", __resp)
        resp = requests.post("http://localhost:5000/reg-er", json={"location":LOCATION, "content":__resp["content"], "level":__resp["level"]})
        print(resp.content)

    # --- Stop Command ---
    #elif "goodbye" in text or "stop" in text or "exit" in text:
    #    speak("Goodbye. Shutting down.")
    #    return False # Stop the loop

    # --- Fallback ---
    else:
        speak("I'm sorry, I don't understand that request. You can ask for 'water', 'blanket', or 'help'.")

    return True


def main():
    global whisper_model

    print("Loading AI model... (This may take a moment on the first run)")
    try:
        """
        whisper_model = WhisperModel(
            MODEL,
            device="cpu",
            compute_type="int8" # This is the key to CPU speed
        )
        """
        #empty_audio = sr.AudioData(b'', 16000, 2)
        #recognizer.recognize_whisper(empty_audio, model=MODEL   )
        pass
    except sr.UnknownValueError:
        pass
    except Exception as e:
        if "No audio data" in str(e):
             pass
        else:
            print(f"Error loading model: {e}")
            return
            
    print("AI Model loaded.")
    speak("Patient assistant is now active.")
    
    running = True
    while running:
        try:
            command = listen_for_command()
            running = process_command(command)
        except KeyboardInterrupt:
            print("\nShutting down via keyboard.")
            running = False
        except Exception as e:
            print(f"A critical error occurred: {e}. Restarting loop.")
            speak("I've run into an error. Please wait a moment and try again.")
            time.sleep(2)

if __name__ == "__main__":
    main()