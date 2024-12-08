# backend/utils/whatsapp.py

import requests
import os
import logging

logger = logging.getLogger(__name__)

WHATSAPP_ACCESS_TOKEN = os.getenv('WHATSAPP_ACCESS_TOKEN')
WHATSAPP_PHONE_NUMBER_ID = os.getenv('WHATSAPP_PHONE_NUMBER_ID')
ADMIN_WHATSAPP_NUMBERS = os.getenv('ADMIN_WHATSAPP_NUMBERS', '').split(',')

def send_whatsapp_message(to_number, message):
    """
    Sends a WhatsApp message to the specified number using the WhatsApp Business API.
    If 'message' is a string, it sends a text message.
    If 'message' is a dict, it assumes it's an interactive or structured message.
    """
    url = f"https://graph.facebook.com/v13.0/{WHATSAPP_PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }

    if isinstance(message, dict):
        # Assuming interactive or structured message
        payload = {
            "messaging_product": "whatsapp",
            "to": to_number,
            **message
        }
    else:
        # Simple text message
        payload = {
            "messaging_product": "whatsapp",
            "to": to_number,
            "type": "text",
            "text": {
                "body": message
            }
        }

    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        logger.info(f"Message sent to {to_number}")
    except requests.exceptions.HTTPError as err:
        logger.error(f"Failed to send message to {to_number}: {err.response.text}")
    except Exception as e:
        logger.error(f"An error occurred while sending message to {to_number}: {str(e)}")

def send_message_to_admin(message):
    """
    Sends a WhatsApp message to all admin numbers listed in the ADMIN_WHATSAPP_NUMBERS environment variable.
    'message' should be a string for a simple text message.
    """
    for admin_number in ADMIN_WHATSAPP_NUMBERS:
        admin_number = admin_number.strip()
        if admin_number:
            send_whatsapp_message(admin_number, message)
