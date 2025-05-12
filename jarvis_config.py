import os
from flask import Flask, request, Response, jsonify
import requests
from dotenv import load_dotenv
from flask_cors import CORS
load_dotenv()
import pygame
import sys
import time
import tempfile
import re
import json

elevenlabs_api_key = os.getenv("ELEVENLABS_API_KEY")
if not elevenlabs_api_key:
    print("Error: ELEVENLABS_API_KEY not found in environment variables")
    print("Please add it to your .env file")
    sys.exit(1)

CALLUM_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "MF3mGyEYCl7XYWbV9V6O")

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


import logging

logging.basicConfig(filename="knowledgebase.log", level=logging.INFO)


def remember_info(name=None, number=None, info=None):
    """
    Store user-provided information in contacts.json (for contacts) or knowledgebase.txt (for other info).

    Args:
        name (str, optional): The name of the contact (e.g., "Shibam").
        number (str, optional): The phone number of the contact (e.g., "1234567890").
        info (str, optional): Non-contact information to store (e.g., "Team meeting tomorrow").

    Returns:
        dict: A dictionary with status and message indicating the result of the operation.
    """
    try:
        if not any([name, number, info]):
            logging.error("No information provided to remember")
            return {
                "status": "error",
                "message": "No information provided to remember."
            }

        if name and number:
            if not re.match(r"^\d{10}$", number):
                logging.error(f"Invalid phone number format: {number}")
                return {
                    "status": "error",
                    "message": f"Phone number must be 10 digits: {number}"
                }

            contacts_file = "contacts.json"
            if os.path.exists(contacts_file):
                with open(contacts_file, "r", encoding="utf-8") as f:
                    contacts = json.load(f)
            else:
                contacts = []
                logging.info(f"Creating new contacts file: {contacts_file}")

            contact_exists = False
            for contact in contacts:
                if contact["name"].lower() == name.lower():
                    contact["phone_number"] = number
                    contact_exists = True
                    logging.info(f"Updated contact: {name} with phone {number}")
                    break

            if not contact_exists:
                contacts.append({"name": name, "phone_number": number})
                logging.info(f"Added new contact: {name} with phone {number}")

            with open(contacts_file, "w", encoding="utf-8") as f:
                json.dump(contacts, f, indent=4)

            return {
                "status": "success",
                "message": f"Saved contact: {name}, {number}"
            }

        if info:
            knowledgebase_file = "knowledgebase.txt"
            if not os.path.exists(knowledgebase_file):
                with open(knowledgebase_file, "w", encoding="utf-8") as f:
                    f.write("# Knowledge Base\n")
                logging.info(f"Created new knowledgebase file: {knowledgebase_file}")

            timestamp = time.ctime()
            entry = f"[{timestamp}] {info}\n"

            with open(knowledgebase_file, "a", encoding="utf-8") as f:
                f.write(entry)

            logging.info(f"Stored info in knowledgebase: {info}")
            return {
                "status": "success",
                "message": f"Successfully remembered: {info}"
            }

        logging.error("Incomplete contact information: both name and number are required")
        return {
            "status": "error",
            "message": "Incomplete contact information: both name and number are required."
        }

    except Exception as e:
        logging.error(f"Failed to store info: {str(e)}")
        return {
            "status": "error",
            "message": f"Failed to store information: {str(e)}"
        }


def recall_info(query):
    """
    Search knowledgebase.txt for information matching the query, with flexible matching for names and email-related terms.

    Args:
        query (str): The search term (e.g., "Shibam's email", "Shibam's email address").

    Returns:
        dict: A dictionary with status, message, and value (if found).
    """
    try:
        knowledgebase_file = "knowledgebase.txt"
        if not os.path.exists(knowledgebase_file):
            logging.error("Knowledge base file does not exist")
            return {
                "status": "error",
                "message": "Knowledge base file does not exist."
            }

        query = query.lower().strip()
        name_match = re.search(r"(\w+)'s\s*(email|gmail|email address)", query)
        search_name = name_match.group(1) if name_match else query.split()[0] if query else ""
        search_terms = ["email", "gmail"]  # Terms to match email-related entries

        with open(knowledgebase_file, "r", encoding="utf-8") as f:
            lines = f.readlines()
        logging.info(f"Knowledgebase contents: {lines}")

        matches = []
        for line in lines:
            line_lower = line.lower().strip()
            if not line.startswith("#") and search_name in line_lower and any(
                    term in line_lower for term in search_terms):
                email_match = re.search(r'[\w\.-]+@[\w\.-]+', line)
                if email_match:
                    matches.append({
                        "entry": line.strip(),
                        "email": email_match.group()
                    })

        if matches:
            latest_match = matches[-1]
            logging.info(f"Found email for query '{query}': {latest_match['email']}")
            return {
                "status": "success",
                "message": f"Found: {latest_match['email']}",
                "value": latest_match['email']
            }
        else:
            logging.error(f"No matching email found for query '{query}'")
            return {
                "status": "error",
                "message": "No matching email found in knowledge base."
            }
    except Exception as e:
        logging.error(f"Failed to recall info for query '{query}': {str(e)}")
        return {
            "status": "error",
            "message": f"Failed to recall information: {str(e)}"
        }

function_declarations = [
    {
        "name": "call",
        "description": "Initiates a phone call to a recipient (by phone number or name) with a specified task using Bland AI API.",
        "parameters": {
            "type": "object",
            "properties": {
                "recipient_no": {"type": "string",
                                 "description": "Recipient's phone number (10 digits, e.g., 1234567890) or name (e.g., Shibam)."},
                "task": {"type": "string", "description": "Name or description of the task for the call."}
            },
            "required": ["recipient_no", "task"]
        }
    },

    {
        "name": "research_topic",
        "description": "Research a topic by searching on Bing, collecting the first 5-6 links, and summarizing their content.",
        "parameters": {
            "type": "object",
            "properties": {
                "topic": {
                    "type": "string",
                    "description": "The topic to research (e.g., 'machine learning advancements')."
                },
                "max_links": {
                    "type": "integer",
                    "description": "Number of links to collect (default 6).",
                    "default": 6
                }
            },
            "required": ["topic"]
        }
    },
    {
        "name": "do_homework",
        "description": "Access the Truman University Brightspace portal to start homework for a specific subject by logging in and navigating to the subject’s course page. Trigger this for commands like 'do my homework for <subject>', 'help with <subject> homework', or 'access my <subject> course'.",
        "parameters": {
            "type": "object",
            "properties": {
                "subject": {
                    "type": "string",
                    "description": "The subject of the homework (e.g., 'Artificial Intelligence', 'Calculus')."
                }
            },
            "required": ["subject"]
        }
    },
    {
        "name": "click_element",
        "description": "Go to a section by clicking a button or a link. Click a button or link on the current webpage by its visible text or partial text match, such as 'Apply', 'Images', 'News', or 'Submit'. Use this for navigation links, buttons, menu items, or tabs (e.g., 'Images' tab on a search results page), but not for search result links. The user can also ask like go to '<link text>'  ",
        "parameters": {
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "The visible text or partial text of the button or link to click (e.g., 'Images', 'Apply'). Case-insensitive."
                }
            },
            "required": ["text"]
        }
    },
    {
        "name": "search_web",
        "description": "Perform a search on Bing with the specified query.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query to enter (e.g., 'python tutorials')."
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "click_youtube_video",
        "description": "Click a YouTube video link on the current webpage, optionally matching a description.",
        "parameters": {
            "type": "object",
            "properties": {
                "description": {
                    "type": "string",
                    "description": "Optional description to match the video title (e.g., 'python tutorial').",
                    "default": ""
                }
            }
        }
    },
    {
        "name": "go_back",
        "description": "Navigate back to the previous page in the browser.",
        "parameters": {
            "type": "object",
            "properties": {}
        }
    },
{
        "name": "scroll_up",
        "description": "scroll up in the current page in the browser.",
        "parameters": {
            "type": "object",
            "properties": {}
        }
    },
{
        "name": "scroll_down",
        "description": "scroll down in the page in the browser.",
        "parameters": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "go_forward",
        "description": "Navigate to the next page in the browser's history, if available.",
        "parameters": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "close_tab",
        "description": "Close the current browser tab and switch to another open tab, if available. Does not close the browser if only one tab is open.",
        "parameters": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "navigate_to_url",
        "description": "Navigate to a specified URL or website (e.g., 'google.com').",
        "parameters": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "The URL or website to navigate to (e.g., 'google.com', 'https://example.com')."
                }
            },
            "required": ["url"]
        }
    },
    {
        "name": "login_truman",
        "description": "Log into any website with provided credentials.",
        "parameters": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "click_search_result_link",
        "description": "Go to a section by clicking a button or a link. Click a search result link on a Bing search results page that contains specific text. Use this only for search result links, not for links on other webpages. If 'first' is specified (e.g., 'click the first link with X'), clicks the first matching link. Lists multiple matches for selection if multiple links are found and first_only is false. The user can also ask like go to '<link text>'",
        "parameters": {
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "Text to search for in the search result link title (e.g., 'University of Example'). Partial matches and typos are supported."
                },
                "first_only": {
                    "type": "boolean",
                    "description": "If true, clicks the first matching link; otherwise, lists all matches if multiple found.",
                    "default": False
                }
            },
            "required": ["text"]
        }
    },

    {
    "name": "process_spotify_command",
    "description": "Control Spotify playback based on user commands.such as playing a specific song or artist, pausing music, skipping to the next track, or stopping playback.",
    "parameters": {
        "type": "object",
        "properties": {
            "text": {
                "type": "string",
                "description": "The user's natural-language command related to Spotify.(e.g., 'Play Bohemian Rhapsody by Queen', 'Pause the music', 'Skip this song')."
            }
        },
        "required": ["text"]
    }
},

{
    "name": "send_email",
    "description": "Send an email via Gmail SMTP server to a recipient specified by either their email address or name (looked up in the knowledge base). Exactly one of recipient_email or recipient_name must be provided.",
    "parameters": {
        "type": "object",
        "properties": {
            "recipient_email": {
                "type": "string",
                "description": "The recipient's email address (e.g., 'recipient@example.com'). Mutually exclusive with recipient_name."
            },
            "recipient_name": {
                "type": "string",
                "description": "The recipient's name to look up in the knowledge base (e.g., 'Shalin'). Mutually exclusive with recipient_email."
            },
            "body": {
                "type": "string",
                "description": "The body of the email message."
            }
        },
        "required": ["body"]
    }
},
    {
        "name": "remember_info",
        "description": "Store user-provided information in a knowledge base file for future reference, creating the file if it doesn't exist. It saves and remembers information",
        "parameters": {
            "type": "object",
            "properties": {
                "info": {
                    "type": "string",
                    "description": "The information to store in the knowledge base (e.g., 'Shalin's phone number is 1029318203')."
                }
            },
            "required": ["info"]
        }
    },
{
    "name": "recall_info",
    "description": "Search the knowledge base for information matching a query.  Whenever user asks question about do you know this or what is this refer to this function.",
    "parameters": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The search term to find in the knowledge base (e.g., 'Shalin's phone number'). "
            }
        },
        "required": ["query"]
    }
}


]