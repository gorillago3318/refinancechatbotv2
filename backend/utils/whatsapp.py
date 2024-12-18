import os
import logging
import requests

# Configure logging for this module
logger = logging.getLogger(__name__)

# Load WhatsApp API credentials from environment variables
WHATSAPP_API_URL = os.getenv('WHATSAPP_API_URL')
WHATSAPP_API_TOKEN = os.getenv('WHATSAPP_API_TOKEN')
WHATSAPP_PHONE_NUMBER_ID = os.getenv('WHATSAPP_PHONE_NUMBER_ID')
ADMIN_WHATSAPP_NUMBERS = [num.strip() for num in os.getenv('ADMIN_WHATSAPP_NUMBERS', '').split(',') if num.strip()]

# Validate environment variables
missing_vars = []
if not WHATSAPP_API_URL:
    missing_vars.append("WHATSAPP_API_URL")
if not WHATSAPP_API_TOKEN:
    missing_vars.append("WHATSAPP_API_TOKEN")
if not WHATSAPP_PHONE_NUMBER_ID:
    missing_vars.append("WHATSAPP_PHONE_NUMBER_ID")

if missing_vars:
    raise EnvironmentError(f"❌ Missing essential WhatsApp API credentials: {', '.join(missing_vars)}. Please check your environment variables.")

def get_headers() -> dict:
    return {
        'Authorization': f'Bearer {WHATSAPP_API_TOKEN}',
        'Content-Type': 'application/json'
    }

def send_whatsapp_message(to_number: str, message: str) -> dict:
    try:
        payload = {
            "messaging_product": "whatsapp",
            "to": to_number,
            "type": "text",
            "text": {"body": message}
        }
        
        response = requests.post(WHATSAPP_API_URL, headers=get_headers(), json=payload)
        response.raise_for_status()

        response_data = response.json()
        logger.info(f"✅ Message sent successfully to {to_number}. Response: {response_data}")
        return {"status": "success", "response": response_data}
    
    except requests.exceptions.HTTPError as e:
        logger.error(f"❌ HTTPError: {e.response.status_code} - {e.response.text}")
        return {"status": "failed", "error": f"HTTPError: {e.response.status_code}"}
    
    except Exception as e:
        logger.error(f"❌ An unexpected error occurred while sending message to {to_number}: {str(e)}")
        return {"status": "failed", "error": str(e)}

def send_message_to_admin(message: str) -> None:
    for admin_number in ADMIN_WHATSAPP_NUMBERS:
        if admin_number:
            send_whatsapp_message(admin_number, message)
