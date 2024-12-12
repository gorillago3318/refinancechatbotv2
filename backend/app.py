import os
import logging
from flask import Flask, request, jsonify

# Configure logging
logging.basicConfig(level=logging.INFO)

def create_app():
    app = Flask(__name__)
    register_routes(app)
    return app

def register_routes(app):
    @app.route('/webhook', methods=['GET', 'POST'])
    def webhook():
        if request.method == 'POST':
            try:
                data = request.json
                logging.info(f"📩 Full request payload: {data}")  # Log full request payload for debugging

                # Extract message data
                value = data.get('entry', [{}])[0].get('changes', [{}])[0].get('value', {})
                messages = value.get('messages', [])
                
                if messages:
                    message = messages[0]
                    phone_number = message.get('from')
                    user_message = message.get('text', {}).get('body', '').strip().lower()
                    
                    logging.info(f"📨 Incoming message from {phone_number}: {user_message}")
                    
                    # If user says 'hi', 'hello', or 'hey', trigger welcome message
                    if user_message in ['hi', 'hello', 'hey']:
                        response_message = (
                            "Hi! Welcome to Finzo, your personal refinancing assistant. 😊\n\n"
                            "Here's how I can help you:\n"
                            "- Get an estimation of your potential savings.\n"
                            "- Provide personalized guidance for refinancing.\n\n"
                            "Let's start by getting your name. Please share your name to proceed."
                        )
                        send_whatsapp_message(phone_number, response_message)
                    
                    # If user's message matches the name pattern, continue to the next step
                    elif is_name(user_message):  
                        response_message = (
                            f"Nice to meet you, {user_message.title()}! 😊\n"
                            "How old are you? (Must be between 18 and 70)"
                        )
                        send_whatsapp_message(phone_number, response_message)
                    
                    # If user's message doesn't match the name or known commands, display help message
                    else:
                        response_message = (
                            "I'm not sure how to respond to that.\n"
                            "You can ask me questions about refinancing, or type 'start' to begin."
                        )
                        send_whatsapp_message(phone_number, response_message)
                
                else:
                    logging.warning(f"⚠️ No messages found in request data. This could be a status update.")
            except Exception as e:
                logging.error(f"❌ Error: {e}")
        return 'OK', 200

def send_whatsapp_message(phone_number, message):
    import requests
    url = f"https://graph.facebook.com/v17.0/{os.getenv('WHATSAPP_PHONE_ID')}/messages"
    headers = {
        'Authorization': f'Bearer {os.getenv("WHATSAPP_API_TOKEN")}',
        'Content-Type': 'application/json'
    }
    payload = {'messaging_product': 'whatsapp', 'to': phone_number, 'type': 'text', 'text': {'body': message}}
    response = requests.post(url, json=payload, headers=headers)
    if response.status_code == 200:
        logging.info(f"✅ Message sent successfully to {phone_number}")
    else:
        logging.error(f"❌ Failed to send message. Response: {response.json()}")

def is_name(text):
    """
    Check if the text is likely a name.
    - Allow names with 1-4 words (e.g., 'Mak Wai Kit', 'John', 'Lee Chong Wei')
    - Ensure it only contains alphabets (names shouldn't have numbers or special characters)
    """
    words = text.split()
    if 1 <= len(words) <= 4 and all(word.isalpha() for word in words):
        return True
    return False
