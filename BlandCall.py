import requests
import re
import os
import json
import logging
from dotenv import load_dotenv
load_dotenv()
BLAND_API_KEY = os.getenv("BlandAPIKey")


def recall_info(query):
    try:
        query = query.lower().strip()
        name_match = re.search(r"(\w+)'s\s*(phone|phone number|number|email|gmail|email address)", query)
        search_name = name_match.group(1) if name_match else query.split()[0] if query else ""
        is_phone_query = name_match and any(term in name_match.group(2) for term in ["phone", "number"])
        is_email_query = name_match and any(term in name_match.group(2) for term in ["email", "gmail"])

        result = {"status": "error", "message": "No matching information found."}

        contacts_file = "contacts.json"
        if os.path.exists(contacts_file) and (is_phone_query or not is_email_query):
            with open(contacts_file, "r", encoding="utf-8") as f:
                contacts = json.load(f)
            for contact in contacts:
                if contact.get("name", "").lower() == search_name:
                    logging.info(f"Found phone number for '{search_name}': {contact['phone_number']}")
                    return {
                        "status": "success",
                        "message": f"Found phone number: {contact['phone_number']}",
                        "value": contact["phone_number"]
                    }

        knowledgebase_file = "knowledgebase.txt"
        if os.path.exists(knowledgebase_file) and (is_email_query or not is_phone_query):
            with open(knowledgebase_file, "r", encoding="utf-8") as f:
                lines = f.readlines()
            logging.info(f"Knowledgebase contents: {lines}")

            search_terms = ["email", "gmail"]
            matches = []
            for line in lines:
                line_lower = line.lower().strip()
                if not line_lower.startswith("#") and search_name in line_lower and any(
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
                    "message": f"Found email: {latest_match['email']}",
                    "value": latest_match["email"]
                }

        logging.error(f"No matching phone number or email found for query '{query}'")
        return result

    except Exception as e:
        logging.error(f"Failed to recall info for query '{query}': {str(e)}")
        return {
            "status": "error",
            "message": f"Failed to recall information: {str(e)}"
        }

def call(recipient_no, task):
    """
    Initiate a phone call via Bland AI API, using a phone number or name to look up the number.

    Args:
        recipient_no (str): Phone number (e.g., "1234567890") or name (e.g., "Name").
        task (str): Name or description of the task for the call.

    Returns:
        dict: Status, message, and details of the call attempt.
    """
    try:
        # Check if recipient_no is a name (not a 10-digit number)
        if not re.match(r"^\d{10}$", recipient_no):
            recall_result = recall_info(recipient_no)
            if recall_result["status"] != "success" or not recall_result["value"].isdigit():
                return {
                    "status": "error",
                    "message": f"Could not find phone number for '{recipient_no}': {recall_result['message']}"
                }
            recipient_number = "+1" + recall_result["value"]
        else:
            recipient_number = "+1" + recipient_no

        caller_id = os.getenv("BlandPhoneNumber")
        task_name = task
        message_text = (
            "<context_from_user>"
        )

        payload = {
            "phone_number": recipient_number,
            "task": task_name,
            "voice": "paige",
            "prompt": {
                "type": "text",
                "text": message_text
            },
            "caller_id": caller_id
        }

        headers = {
            "Authorization": f"Bearer {os.environ['BLAND_API_KEY']}",
            "Content-Type": "application/json"
        }

        response = requests.post("https://api.bland.ai/v1/calls", json=payload, headers=headers)

        if response.status_code == 200:
            return {
                "status": "success",
                "message": f"Call initiated successfully to {recipient_number}.",
                "details": response.json()
            }
        else:
            return {
                "status": "failure",
                "message": f"Call failed: {response.status_code} {response.text}"
            }

    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to initiate call: {str(e)}"
        }




