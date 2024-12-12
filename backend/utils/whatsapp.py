import requests
import os
import logging

logger = logging.getLogger(__name__)

# Load WhatsApp API credentials from environment variables
WHATSAPP_API_URL = os.getenv('WHATSAPP_API_URL', 'https://graph.facebook.com/v16.0/your-number-id/messages')
WHATSAPP_API_TOKEN = os.getenv('WHATSAPP_API_TOKEN', 'your_default_token')
WHATSAPP_PHONE_NUMBER_ID = os.getenv('WHATSAPP_PHONE_NUMBER_ID', 'your-phone-id')
ADMIN_WHATSAPP_NUMBERS = os.getenv('ADMIN_WHATSAPP_NUMBERS', '').split(',')

HEADERS = {
    'Authorization': f'Bearer {WHATSAPP_API_TOKEN}',
    'Content-Type': 'application/json'
}

def send_whatsapp_message(to_number, message):
    """Send a WhatsApp message to the specified number using the WhatsApp Business API."""
    try:
        url = f"https://graph.facebook.com/v16.0/{WHATSAPP_PHONE_NUMBER_ID}/messages"
        
        if isinstance(message, dict):
            # Interactive or structured message
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
                "text": {"body": message}
            }
        
        response = requests.post(url, headers=HEADERS, json=payload)
        response.raise_for_status()
        logger.info(f"Message sent to {to_number}")
        return {
            "status": "success",
            "response": response.json()
        }
    except requests.exceptions.HTTPError as err:
        logger.error(f"Failed to send message to {to_number}: {err.response.text}")
        return {
            "status": "failed",
            "error": err.response.text
        }
    except Exception as e:
        logger.error(f"An error occurred while sending message to {to_number}: {str(e)}")
        return {
            "status": "failed",
            "error": str(e)
        }

def format_phone_number(raw_phone_number):
    """Format phone numbers to the WhatsApp API standard (E.164 format)."""
    try:
        formatted_number = raw_phone_number.replace(" ", "").replace("-", "").replace("+", "")
        if not formatted_number.startswith("6"):  # Assuming Malaysian numbers (e.g., 60123456789)
            formatted_number = f"6{formatted_number}"
        return formatted_number
    except Exception as e:
        logger.error(f"Error formatting phone number {raw_phone_number}: {e}")
        return None

def send_template_message(phone_number, template_name, language_code="en_US", components=None):
    """Send a pre-approved template message via the WhatsApp API."""
    try:
        payload = {
            "messaging_product": "whatsapp",
            "to": phone_number,
            "type": "template",
            "template": {
                "name": template_name,
                "language": {"code": language_code},
                "components": components if components else []
            }
        }
        
        response = requests.post(WHATSAPP_API_URL, json=payload, headers=HEADERS)
        response.raise_for_status()
        
        logger.info(f"Template message sent to {phone_number} with template {template_name}")
        return {
            "status": "success",
            "response": response.json()
        }
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to send template message to {phone_number}: {e}")
        return {
            "status": "failed",
            "error": str(e)
        }

def send_message_to_admin(message):
    """Send a WhatsApp message to all admin numbers listed in the ADMIN_WHATSAPP_NUMBERS environment variable."""
    for admin_number in ADMIN_WHATSAPP_NUMBERS:
        admin_number = admin_number.strip()
        if admin_number:
            send_whatsapp_message(admin_number, message)
