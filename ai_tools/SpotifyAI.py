import os
import sys
import subprocess
import json
import time
import requests
import tempfile
import pygame
import random
from dotenv import load_dotenv

DEBUG = True

process_running = False


def debug_print(message):
    """Print debug messages if debugging is enabled"""
    if DEBUG:
        print(f"DEBUG: {message}")


load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    print("Error: GEMINI_API_KEY not found in environment variables")
    print("Please create a .env file with your GEMINI_API_KEY")
    sys.exit(1)

elevenlabs_api_key = os.getenv("ELEVENLABS_API_KEY")
if not elevenlabs_api_key:
    print("Error: ELEVENLABS_API_KEY not found in environment variables")
    print("Please add it to your .env file")
    sys.exit(1)

CALLUM_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "MF3mGyEYCl7XYWbV9V6O")

pygame.mixer.init()


SPOTIFY_PATHS = [
    "C:\\Program Files\\WindowsApps\\SpotifyAB.SpotifyMusic_1.262.580.0_x64__zpdnekdrzrea0\\Spotify.exe",
    "C:\\Users\\{}\\AppData\\Roaming\\Spotify\\Spotify.exe".format(os.getenv('USERNAME')),
    "C:\\Program Files\\WindowsApps\\SpotifyAB.SpotifyMusic_1.227.883.0_x86__zpdnekdrzrea0\\Spotify.exe",
    "C:\\Program Files (x86)\\Spotify\\Spotify.exe"
]


custom_path = os.getenv("SPOTIFY_PATH")
if custom_path:
    SPOTIFY_PATHS.insert(0, custom_path)



def get_process_state():
    """Returns whether the assistant is currently processing a command"""
    global process_running
    return process_running


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
                    time.sleep(0.5)  # Give system time to release the file
                    os.remove(temp_audio_path)
                except Exception as e:
                    print(f"Warning: Could not remove temp file: {e}")
            except Exception as e:
                print(f"Error playing audio: {e}")
        else:
            print(f"Error with ElevenLabs API: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"Error using ElevenLabs API: {e}")


def get_spotify_path():
    """Find the correct Spotify executable path"""
    for path in SPOTIFY_PATHS:
        if os.path.exists(path):
            return path
    return None


def process_command_with_gemini(user_input):
    """Use Gemini 2.0 Flash to interpret the user command and format it for Spotify control"""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}"

    prompt = f"""
    Extract the Spotify command from this user input: "{user_input}"
    Return a JSON with the following structure:
    {{
        "command": "play" | "pause" | "next" | "previous" | "repeat" | "open" | "close" | "volume",
        "song": "song name" or null,
        "artist": "artist name" or null,
        "volume_level": integer between 0-100 or null
    }}

    Supported commands and their meanings:
    - "play": Play a song (with optional song name and artist)
    - "pause": Pause the current playback
    - "next": Skip to the next track
    - "previous": Go back to the previous track
    - "repeat": Toggle repeat mode
    - "open": Launch Spotify
    - "close": Close Spotify
    - "volume": Adjust the volume (requires volume_level as percentage, e.g., 50 for 50%)

    Only include relevant fields based on the user's request.

    IMPORTANT RULES:
    1. If the user asks to adjust volume, return command "volume" with the requested volume_level.
    2. If the user asks to mute or unmute, return command "volume" with volume_level 0 or 50 respectively.
    3. If the command is to play a random song or is a generic play request without a specific song named, 
    select a song that Tony Stark from Iron Man would listen to, such as classic rock songs, heavy metal, or modern rock hits.

    Tony Stark song examples:
    - "Back in Black" by AC/DC
    - "Shoot to Thrill" by AC/DC
    - "Highway to Hell" by AC/DC
    - "Iron Man" by Black Sabbath
    - "Paranoid" by Black Sabbath
    - "Sharp Dressed Man" by ZZ Top
    - "War Machine" by KISS
    - "Welcome to the Jungle" by Guns N' Roses
    - "Thunder" by Imagine Dragons
    - "Whatever It Takes" by Imagine Dragons

    Choose a different song each time for variety.
    """

    payload = {
        "contents": [
            {
                "parts": [
                    {
                        "text": prompt
                    }
                ]
            }
        ]
    }

    headers = {
        "Content-Type": "application/json"
    }

    try:
        response = requests.post(url, json=payload, headers=headers)

        if response.status_code != 200:
            print(f"Error with Gemini API: {response.status_code} - {response.text}")
            return {"command": "unknown"}

        response_data = response.json()

        if "candidates" in response_data and len(response_data["candidates"]) > 0:
            candidate = response_data["candidates"][0]
            if "content" in candidate and "parts" in candidate["content"]:
                text_content = candidate["content"]["parts"][0]["text"]

                json_text = text_content
                if "```json" in text_content:
                    json_text = text_content.split("```json")[1].split("```")[0].strip()
                elif "```" in text_content:
                    json_text = text_content.split("```")[1].strip()

                try:
                    command_data = json.loads(json_text)
                    return command_data
                except json.JSONDecodeError as e:
                    print(f"Error parsing JSON: {e}")
                    print(f"Raw JSON text: {json_text}")

                    if "play" in user_input.lower():
                        tony_playlist = suggest_tony_stark_playlist()
                        selected_song = random.choice(tony_playlist)
                        return {
                            "command": "play",
                            "song": selected_song["song"],
                            "artist": selected_song["artist"]
                        }

                    return {"command": "unknown"}

        print("Unexpected response structure from Gemini API")
        if "play" in user_input.lower():
            tony_playlist = suggest_tony_stark_playlist()
            selected_song = random.choice(tony_playlist)
            return {
                "command": "play",
                "song": selected_song["song"],
                "artist": selected_song["artist"]
            }
        return {"command": "unknown"}
    except Exception as e:
        print(f"Error processing command with Gemini: {e}")
        if "play" in user_input.lower():
            tony_playlist = suggest_tony_stark_playlist()
            selected_song = random.choice(tony_playlist)
            return {
                "command": "play",
                "song": selected_song["song"],
                "artist": selected_song["artist"]
            }
        return {"command": "unknown"}


def suggest_tony_stark_playlist():
    """Return a curated list of songs that Tony Stark would listen to"""
    tony_stark_favorites = [
        {"song": "Back in Black", "artist": "AC/DC"},
        {"song": "Shoot to Thrill", "artist": "AC/DC"},
        {"song": "Highway to Hell", "artist": "AC/DC"},
        {"song": "Thunderstruck", "artist": "AC/DC"},
        {"song": "Iron Man", "artist": "Black Sabbath"},
        {"song": "Paranoid", "artist": "Black Sabbath"},
        {"song": "War Pigs", "artist": "Black Sabbath"},
        {"song": "Sharp Dressed Man", "artist": "ZZ Top"},
        {"song": "War Machine", "artist": "KISS"},
        {"song": "Welcome to the Jungle", "artist": "Guns N' Roses"},
        {"song": "Paradise City", "artist": "Guns N' Roses"},
        {"song": "Sweet Child O' Mine", "artist": "Guns N' Roses"},
        {"song": "Seven Nation Army", "artist": "The White Stripes"},
        {"song": "Thunder", "artist": "Imagine Dragons"},
        {"song": "Whatever It Takes", "artist": "Imagine Dragons"},
        {"song": "Sabotage", "artist": "Beastie Boys"},
        {"song": "For Those About To Rock", "artist": "AC/DC"},
        {"song": "Enter Sandman", "artist": "Metallica"},
        {"song": "The Pretender", "artist": "Foo Fighters"},
        {"song": "Just Like Fire", "artist": "Pink"}
    ]
    return tony_stark_favorites


def is_spotify_running():
    """Check if Spotify is currently running"""
    try:
        result = subprocess.run(
            ['tasklist', '/FI', 'IMAGENAME eq Spotify.exe'],
            capture_output=True,
            text=True
        )
        return 'Spotify.exe' in result.stdout
    except Exception as e:
        print(f"Error checking Spotify status: {e}")
        return False


def open_spotify():
    """Open Spotify application"""
    if not is_spotify_running():
        try:
            spotify_path = get_spotify_path()

            if spotify_path:
                try:
                    subprocess.Popen([spotify_path])
                    speak(jarvis_response("open"))
                    time.sleep(2)
                    return True
                except PermissionError:
                    print("Permission denied to access Spotify executable. Trying alternative method...")
                except Exception as e:
                    print(f"Error launching Spotify directly: {e}")

            try:
                subprocess.Popen(["explorer.exe", "spotify:"])
                speak(jarvis_response("open"))
                time.sleep(2)
                return True
            except Exception as store_err:
                print(f"Error launching via protocol: {store_err}")

                try:
                    subprocess.Popen("start spotify", shell=True)
                    speak(jarvis_response("open"))
                    time.sleep(2)
                    return True
                except Exception as start_err:
                    print(f"Error launching via Start Menu: {start_err}")

            speak(
                "I couldn't find Spotify installed on your system, sir. Please check your installation or try launching it manually.")
            return False
        except Exception as e:
            print(f"Error opening Spotify: {e}")
            speak("I'm afraid I encountered an issue opening Spotify, sir. Please check the installation path.")
            return False
    else:
        speak("Spotify is already running, sir. No need to launch it again.")
        return True


def close_spotify():
    """Close Spotify application"""
    if is_spotify_running():
        try:
            subprocess.run(['taskkill', '/F', '/IM', 'Spotify.exe'],
                           capture_output=True)
            speak(jarvis_response("close"))
            return True
        except Exception as e:
            print(f"Error closing Spotify: {e}")
            speak("I encountered an issue while trying to close Spotify, sir. May I suggest a manual intervention?")
            return False
    else:
        speak("Spotify is not currently running, sir. Nothing to close.")
        return True


def jarvis_response(command, song=None, artist=None, volume=None):
    """Generate a JARVIS-like response based on the command"""
    responses = {
        "open": "Opening Spotify for you, sir. Ready to enhance your auditory experience.",
        "close": "Shutting down Spotify as requested. Is there anything else you need?",
        "play": "Playing music for you now, sir.",
        "pause": "Pausing your music. The silence can be deafening, can't it?",
        "next": "Skipping to the next track. I hope this one suits your taste better.",
        "previous": "Going back to the previous track. Good choice, sir.",
        "repeat": "Toggling repeat mode. Some things are worth experiencing more than once."
    }

    if command == "volume" and volume is not None:
        if volume == 0:
            return "Muting the audio, sir. Silence can be golden at times."
        elif volume <= 30:
            return f"Setting volume to {volume}%. A subtle background ambiance, sir."
        elif volume <= 70:
            return f"Volume adjusted to {volume}%. A comfortable listening level, sir."
        else:
            return f"Volume increased to {volume}%. I hope your neighbors are fans of your music taste, sir."

    tony_stark_artists = ["AC/DC", "Black Sabbath", "ZZ Top", "KISS", "Guns N' Roses",
                          "Imagine Dragons", "Metallica", "The White Stripes", "Foo Fighters"]

    if command == "play" and song:
        if artist and any(band in artist for band in tony_stark_artists):
            stark_responses = [
                f"Playing {song} by {artist}. One of Mr. Stark's favorites, if I may say so.",
                f"Ah, {song} by {artist}. A selection worthy of the Iron Man himself.",
                f"Playing {song} by {artist}. Mr. Stark would approve of your musical taste, sir.",
                f"Excellent choice with {song} by {artist}. This one always gets Mr. Stark into his workshop groove.",
                f"Selecting {song} by {artist}. A most suitable soundtrack for genius work, sir."
            ]
            return random.choice(stark_responses)
        elif artist:
            return f"Playing {song} by {artist}. Excellent choice, sir."
        else:
            return f"Playing {song} for you now. Enjoy, sir."

    return responses.get(command, "Command executed, sir. Would there be anything else?")


def control_spotify(command_data, user_query=""):
    """Control Spotify based on the command data"""
    command = command_data.get("command", "").lower()
    song = command_data.get("song")
    artist = command_data.get("artist")
    volume_level = command_data.get("volume_level")

    debug_print(f"Command: {command}, Song: {song}, Artist: {artist}, Volume: {volume_level}")

    if command == "play" and (user_query.lower() == "suggest tony stark songs" or
                              "tony stark" in user_query.lower() or
                              ("iron man" in user_query.lower() and "playlist" in user_query.lower())):
        tony_playlist = suggest_tony_stark_playlist()
        selected_song = random.choice(tony_playlist)
        song = selected_song["song"]
        artist = selected_song["artist"]
        speak(
            f"I've selected some music I believe Mr. Stark would appreciate. {song} by {artist} should be fitting, sir.")

    if command == "open":
        return open_spotify()

    elif command == "close":
        result = close_spotify()
        if result:
            speak("Shutting down Spotify assistant as well. Goodbye, sir.")
            time.sleep(1)
            sys.exit(0)
        return result

    elif command == "volume" and volume_level is not None:
        try:
            volume_percent = min(100, max(0, volume_level))


            if volume_percent == 0:

                ps_command = "$obj = New-Object -ComObject WScript.Shell; $obj.SendKeys([char]173)"
            else:

                unmute_command = "$obj = New-Object -ComObject WScript.Shell; $obj.SendKeys([char]173); Start-Sleep -m 100; $obj.SendKeys([char]173)"
                subprocess.run(["powershell", "-Command", unmute_command], capture_output=True)


                min_vol_cmd = "for ($i=0; $i -lt 50; $i++) { $obj = New-Object -ComObject WScript.Shell; $obj.SendKeys([char]174) }"
                subprocess.run(["powershell", "-Command", min_vol_cmd], capture_output=True)


                vol_steps = volume_percent // 2
                vol_up_cmd = f"for ($i=0; $i -lt {vol_steps}; $i++) {{ $obj = New-Object -ComObject WScript.Shell; $obj.SendKeys([char]175); Start-Sleep -m 20 }}"
                subprocess.run(["powershell", "-Command", vol_up_cmd], capture_output=True)

            speak(jarvis_response("volume", volume=volume_level))
            return True
        except Exception as e:
            print(f"Error adjusting volume: {e}")
            speak("I'm experiencing some difficulties adjusting the volume, sir.")
            return False

    elif command in ["play", "pause", "next", "previous", "repeat"]:
        if not is_spotify_running():
            if not open_spotify():
                return False
            time.sleep(3)

        if command == "play" and song and artist:
            try:
                debug_print("Checking for direct song URI")

                song_uris = {
                    ("Thunder", "Imagine Dragons"): "spotify:track:57bgtoPSgt236HzfBOd8kj",
                    ("Iron Man", "Black Sabbath"): "spotify:track:20KuVPbQ9LHX5prZKGgFqk",
                    ("Back in Black", "AC/DC"): "spotify:track:08mG3Y1vljYA6bvDt4Wqkj",
                    ("Highway to Hell", "AC/DC"): "spotify:track:2zYzyRzz6pRmhPzyfMEC8s",
                    ("Shoot to Thrill", "AC/DC"): "spotify:track:0C80GCp0mMuBzLf3EAXqxv",
                    ("Thunderstruck", "AC/DC"): "spotify:track:57bgtoPSgt236HzfBOd8kj",
                    ("Paranoid", "Black Sabbath"): "spotify:track:1Vq8aHlGEcGQTGAQTIrW7F",
                    ("Welcome to the Jungle", "Guns N' Roses"): "spotify:track:4CeeEOM32jQcH3eN9Q2dGj"
                }

                if (song, artist) in song_uris:
                    debug_print(f"Found direct URI for {song} by {artist}")
                    uri = song_uris[(song, artist)]
                    subprocess.Popen(["explorer.exe", uri])
                    time.sleep(1.5)
                    speak(jarvis_response("play", song, artist))
                    return True
            except Exception as uri_error:
                debug_print(f"Direct URI failed: {uri_error}")

        if command == "play" and song:
            try:
                if artist:
                    search_term = f'"{song}" artist:"{artist}"'
                else:
                    search_term = f'"{song}"'

                # Focus Spotify
                debug_print("Focusing Spotify window")
                os.system(
                    'powershell -command "$wshell = New-Object -ComObject wscript.shell; $wshell.AppActivate(\'Spotify\')"')
                time.sleep(0.5)

                # Try the search bar method
                # Ctrl+L to focus search
                debug_print("Focusing search bar with Ctrl+L")
                os.system(
                    'powershell -command "$wshell = New-Object -ComObject wscript.shell; $wshell.SendKeys(\'^l\')"')
                time.sleep(0.5)

                # Clear existing text with Ctrl+A and Delete
                debug_print("Clearing search bar")
                os.system(
                    'powershell -command "$wshell = New-Object -ComObject wscript.shell; $wshell.SendKeys(\'^a\')"')
                time.sleep(0.2)
                os.system(
                    'powershell -command "$wshell = New-Object -ComObject wscript.shell; $wshell.SendKeys(\'{DELETE}\')"')
                time.sleep(0.2)

                # Type exact search string (with quotes to be precise)
                debug_print(f"Typing search term: {search_term}")
                os.system(
                    f'powershell -command "$wshell = New-Object -ComObject wscript.shell; $wshell.SendKeys(\'{search_term}\')"')
                time.sleep(1)

                # Press Enter to search
                debug_print("Pressing Enter to search")
                os.system(
                    'powershell -command "$wshell = New-Object -ComObject wscript.shell; $wshell.SendKeys(\'~\')"')
                time.sleep(2)


                debug_print("Navigating to search results")
                for _ in range(5):
                    os.system(
                        'powershell -command "$wshell = New-Object -ComObject wscript.shell; $wshell.SendKeys(\'{TAB}\')"')
                    time.sleep(0.2)

                # Press Down to get to the first song in the list
                for _ in range(2):  # Down arrows to reach the first song
                    os.system(
                        'powershell -command "$wshell = New-Object -ComObject wscript.shell; $wshell.SendKeys(\'{DOWN}\')"')
                    time.sleep(0.2)

                # Press Enter to select and play the song
                debug_print("Pressing Enter to play selected song")
                os.system(
                    'powershell -command "$wshell = New-Object -ComObject wscript.shell; $wshell.SendKeys(\'~\')"')
                time.sleep(0.5)

                speak(jarvis_response("play", song, artist))
            except Exception as e:
                print(f"Error searching for song: {e}")
                speak("I'm having trouble locating that song, sir. Perhaps we should try a different approach.")
                return False
        else:
            # Use Spotify-specific keyboard shortcuts
            try:
                os.system(
                    'powershell -command "$wshell = New-Object -ComObject wscript.shell; $wshell.AppActivate(\'Spotify\')"')
                time.sleep(0.5)

                if command == "play" or command == "pause":
                    debug_print("Toggling play/pause with Space key")
                    os.system(
                        'powershell -command "$wshell = New-Object -ComObject wscript.shell; $wshell.SendKeys(\' \')"')
                    speak(jarvis_response(command))
                elif command == "next":
                    debug_print("Skipping to next track with Ctrl+Right")
                    os.system(
                        'powershell -command "$wshell = New-Object -ComObject wscript.shell; $wshell.SendKeys(\'^{RIGHT}\')"')
                    speak(jarvis_response("next"))
                elif command == "previous":
                    debug_print("Going to previous track with Ctrl+Left")
                    os.system(
                        'powershell -command "$wshell = New-Object -ComObject wscript.shell; $wshell.SendKeys(\'^{LEFT}\')"')
                    speak(jarvis_response("previous"))
                elif command == "repeat":
                    # Ctrl+R for repeat
                    debug_print("Toggling repeat with Ctrl+R")
                    os.system(
                        'powershell -command "$wshell = New-Object -ComObject wscript.shell; $wshell.SendKeys(\'^r\')"')
                    speak(jarvis_response("repeat"))
            except Exception as e:
                print(f"Error controlling Spotify: {e}")
                speak(
                    "I'm experiencing some difficulties controlling Spotify at the moment, sir. Perhaps a system reboot is in order?")
                return False
    else:
        print(f"Unknown command: {command}")
        speak("I'm afraid I don't understand that command, sir. Perhaps you could rephrase?")
        return False

    return True


def process_spotify_command(text):
    """Process a user command for Spotify - function that can be called from frontend"""
    global process_running

    try:
        process_running = True

        if text.lower() in ["exit", "quit", "stop"]:
            process_running = False
            return {"status": "success", "message": "Shutdown complete", "command": "exit"}

        command_data = process_command_with_gemini(text)
        debug_print(f"Gemini response: {command_data}")

        result = control_spotify(command_data, text)

        process_running = False

        if result:
            return {
                "status": "success",
                "message": "Command executed successfully",
                "command": command_data.get("command"),
                "song": command_data.get("song"),
                "artist": command_data.get("artist")
            }
        else:
            return {
                "status": "error",
                "message": "Failed to execute command",
                "command": command_data.get("command")
            }

    except Exception as e:
        process_running = False
        print(f"Error processing command: {e}")
        return {"status": "error", "message": str(e), "command": "unknown"}


def run_interactive_mode():
    """Run the assistant in interactive command line mode"""
    print("Spotify Assistant ready! Enter your commands:")
    print("(Type 'exit' to quit)")

    speak("JARVIS online. Spotify control module activated. How may I assist you today, sir?")

    while True:
        try:
            user_input = input("\nWhat would you like to do with Spotify? ").strip()

            result = process_spotify_command(user_input)

            if result["command"] == "exit":
                break

        except KeyboardInterrupt:
            print("\nDetected keyboard interrupt. Shutting down...")
            speak("Emergency shutdown initiated. Goodbye, sir.")
            break
        except Exception as e:
            print(f"Unexpected error: {e}")
            speak("I've encountered an unexpected error, sir. Shall we try again?")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--import-only":
        print("Spotify Assistant module loaded - ready for frontend integration")
    else:
        run_interactive_mode()