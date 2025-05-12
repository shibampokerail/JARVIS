# Sender email credentials
 # Use an App Password if using Gmail with 2FA
import time
import os
from dotenv import load_dotenv
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import re
from bot.jarvis_config import recall_info
load_dotenv()


def send_email(recipient_email=None, recipient_name=None, body=None):
    """
    Send an email via Gmail SMTP server to a recipient specified by email or name.

    Args:
        recipient_email (str, optional): The recipient's email address.
        recipient_name (str, optional): The recipient's name to look up in the knowledge base.
        body (str): The body of the email.

    Returns:
        dict: A dictionary with status and message indicating the result of the operation.
    """
    smtp_server = "smtp.gmail.com"
    smtp_port = 587
    sender_email = os.getenv("SENDER_GMAIL")
    app_password = os.getenv("EMAIL_APP_PASSWORD")
    subject = "JARVIS"
    full_body = f"{body}\n{time.ctime()}" if body else f"Message from JARVIS\n{time.ctime()}"

    # Validate sender credentials
    if not sender_email or not app_password:
        return {
            "status": "error",
            "message": "Sender email or app password not configured in environment variables."
        }

    # Validate recipient: exactly one of recipient_email or recipient_name must be provided
    if (recipient_email and recipient_name) or (not recipient_email and not recipient_name):
        return {
            "status": "error",
            "message": "Exactly one of recipient_email or recipient_name must be provided."
        }

    # Determine recipient email
    final_recipient_email = None
    if recipient_email:
        # Validate email format
        if re.match(r'^[\w\.-]+@[\w\.-]+$', recipient_email):
            final_recipient_email = recipient_email
        else:
            return {
                "status": "error",
                "message": f"Invalid email format: {recipient_email}"
            }
    elif recipient_name:
        # Look up email in knowledge base using a consistent query
        query = f"{recipient_name}'s email"
        result = recall_info(query)
        if result["status"] == "success":
            final_recipient_email = result["value"]
        else:
            return {
                "status": "error",
                "message": f"I was unable to send the email because I couldn't find an email address for {recipient_name}. Do you want me to try sending it to a specific email address?"
            }

    # Create the email
    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = final_recipient_email
    msg['Subject'] = subject
    msg.attach(MIMEText(full_body, 'plain'))

    # Connect to Gmail's SMTP server
    try:
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(sender_email, app_password)
        server.sendmail(sender_email, final_recipient_email, msg.as_string())
        return {
            "status": "success",
            "message": f"Email sent successfully to {final_recipient_email}!"
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to send email: {str(e)}"
        }
    finally:
        server.quit()