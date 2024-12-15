import os
import logging
import requests  # Import requests to send an HTTP request to WhatsApp API

# Configure logging for this module
logger = logging.getLogger(__name__)

# Load WhatsApp API credentials from environment variables
WHATSAPP_API_URL = os.getenv('WHATSAPP_API_URL')
WHATSAPP_API_TOKEN = os.getenv('WHATSAPP_API_TOKEN')
WHATSAPP_PHONE_NUMBER_ID = os.getenv('WHATSAPP_PHONE_NUMBER_ID')
ADMIN_WHATSAPP_NUMBERS = os.getenv('ADMIN_WHATSAPP_NUMBERS', '').split(',')

# Validate environment variables
if not WHATSAPP_API_URL or not WHATSAPP_API_TOKEN or not WHATSAPP_PHONE_NUMBER_ID:
    raise EnvironmentError("❌ Missing essential WhatsApp API credentials. Check WHATSAPP_API_URL, WHATSAPP_API_TOKEN, and WHATSAPP_PHONE_NUMBER_ID in your environment variables.")

# Create request headers dynamically
def get_headers():
    return {
        'Authorization': f'Bearer {WHATSAPP_API_TOKEN}',
        'Content-Type': 'application/json'
    }

def send_whatsapp_message(to_number: str, message: str) -> dict:
    """
    Send a WhatsApp message to the specified number using the WhatsApp Business API.
    
    Args:
        to_number (str): The recipient's phone number in E.164 format.
        message (str or dict): The message body or interactive message payload.
        
    Returns:
        dict: A status dictionary containing 'status' and 'response'.
    """
    try:
        url = f"https://graph.facebook.com/v16.0/{WHATSAPP_PHONE_NUMBER_ID}/messages"
        
        if isinstance(message, dict):
            payload = {
                "messaging_product": "whatsapp",
                "to": to_number,
                **message
            }
        else:
            payload = {
                "messaging_product": "whatsapp",
                "to": to_number,
                "type": "text",
                "text": {"body": message}
            }
        
        logger.info(f"📤 Sending message to WhatsApp API: {payload}")
        
        response = requests.post(url, headers=get_headers(), json=payload)
        response.raise_for_status()
        
        try:
            response_data = response.json()
        except ValueError as e:
            logger.error(f"❌ Response is not valid JSON: {response.text}")
            return {"status": "failed", "error": "Response is not valid JSON"}
        
        logger.info(f"✅ Message sent successfully to {to_number}. Response: {response_data}")
        return {"status": "success", "response": response_data}
    
    except requests.exceptions.HTTPError as err:
        logger.error(f"❌ Failed to send message to {to_number}. HTTPError: {err.response.text}")
        return {"status": "failed", "error": err.response.text}
    
    except Exception as e:
        logger.error(f"❌ An unexpected error occurred while sending message to {to_number}: {str(e)}")
        return {"status": "failed", "error": str(e)}


def format_phone_number(raw_phone_number: str) -> str:
    """
    Format phone numbers to the WhatsApp API standard (E.164 format).
    
    Args:
        raw_phone_number (str): The phone number to be formatted.
        
    Returns:
        str: The formatted phone number.
    """
    try:
        formatted_number = raw_phone_number.replace(" ", "").replace("-", "").replace("+", "")
        if not formatted_number.startswith("6"):  # Assuming Malaysian numbers
            formatted_number = f"6{formatted_number}"
        logger.info(f"📞 Formatted phone number: {formatted_number}")
        return formatted_number
    except Exception as e:
        logger.error(f"❌ Error formatting phone number {raw_phone_number}: {e}")
        return None

def send_template_message(phone_number: str, template_name: str, language_code: str = "en_US", components: list = None) -> dict:
    """
    Send a pre-approved template message via the WhatsApp API.
    
    Args:
        phone_number (str): The phone number to send the template to.
        template_name (str): The name of the pre-approved template.
        language_code (str, optional): The language code (default is 'en_US').
        components (list, optional): Components for the template message.
        
    Returns:
        dict: A status dictionary containing 'status' and 'response'.
    """
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
        
        logger.info(f"📤 Sending template message to WhatsApp API: {payload}")
        
        response = requests.post(WHATSAPP_API_URL, json=payload, headers=get_headers())
        response.raise_for_status()
        
        try:
            response_data = response.json()
        except ValueError as e:
            logger.error(f"❌ Response is not valid JSON: {response.text}")
            return {"status": "failed", "error": "Response is not valid JSON"}
        
        logger.info(f"✅ Template message sent to {phone_number} with template {template_name}")
        return {"status": "success", "response": response_data}
    
    except requests.exceptions.RequestException as e:
        logger.error(f"❌ Failed to send template message to {phone_number}: {e}")
        return {"status": "failed", "error": str(e)}

def send_message_to_admin(message: str) -> None:
    """
    Send a WhatsApp message to all admin numbers listed in the ADMIN_WHATSAPP_NUMBERS environment variable.
    
    Args:
        message (str): The message to send to the admins.
    """
    for admin_number in ADMIN_WHATSAPP_NUMBERS:
        admin_number = admin_number.strip()
        if admin_number:
            send_whatsapp_message(admin_number, message)
