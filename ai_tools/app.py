import os
import requests
from dotenv import load_dotenv
import pygame
import sys
import time
import tempfile

load_dotenv()


elevenlabs_api_key = os.getenv("ELEVENLABS_API_KEY")
if not elevenlabs_api_key:
    print("Error: ELEVENLABS_API_KEY not found in environment variables")
    print("Please add it to your .env file")
    sys.exit(1)

CALLUM_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "MF3mGyEYCl7XYWbV9V6O")  # Default to Callum if not specified

pygame.mixer.init()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
current_process = ""

def speak(text):
    """Use ElevenLabs API to convert text to speech with Callum's voice and play it"""
    print(f"JARVIS: {text}")


    if not elevenlabs_api_key or elevenlabs_api_key == "your_elevenlabs_api_key_here":
        print("No valid ElevenLabs API key. Skipping voice synthesis.")
        return

    url = f"https://api.elevenlabs.io/v1/text-to-speech/{CALLUM_VOICE_ID}"

    headers = {
        "Accept": "audio/mpeg",
        "Content-Type": "application/json",
        "xi-api-key": elevenlabs_api_key
    }

    data = {
        "text": text,
        "model_id": "eleven_monolingual_v1",
        "voice_settings": {
            "stability": 0.5,
            "similarity_boost": 0.8
        }
    }

    try:
        response = requests.post(url, json=data, headers=headers)

        if response.status_code == 200:
            temp_audio_path = os.path.join(tempfile.gettempdir(), f"jarvis_speech_{int(time.time())}.mp3")

            with open(temp_audio_path, "wb") as temp_audio:
                temp_audio.write(response.content)

            try:
                pygame.mixer.music.load(temp_audio_path)
                pygame.mixer.music.play()
                while pygame.mixer.music.get_busy():
                    pygame.time.Clock().tick(10)

                try:
                    pygame.mixer.music.unload()
                    time.sleep(0.5)
                    os.remove(temp_audio_path)
                except Exception as e:
                    print(f"Warning: Could not remove temp file: {e}")
            except Exception as e:
                print(f"Error playing audio: {e}")
        else:
            print(f"Error with ElevenLabs API: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"Error using ElevenLabs API: {e}")