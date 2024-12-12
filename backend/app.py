import os
import logging
from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy

# Initialize the database globally
db = SQLAlchemy()

# Configure logging
logging.basicConfig(level=logging.INFO)

def create_app():
    app = Flask(__name__)
    database_url = os.getenv('DATABASE_URL', '')
    if database_url.startswith('postgres://'):
        database_url = database_url.replace('postgres://', 'postgresql://', 1)
    app.config['SQLALCHEMY_DATABASE_URI'] = database_url
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    db.init_app(app)
    register_routes(app)
    return app

def register_routes(app):
    @app.route('/webhook', methods=['GET', 'POST'])
    def webhook():
        if request.method == 'GET':
            token = request.args.get('hub.verify_token')
            if token == os.getenv('VERIFY_TOKEN'):
                logging.info("✅ Webhook verified successfully!")
                return request.args.get('hub.challenge')
            return 'Invalid verify token', 403
        
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
                    
                    if user_message in ['hi', 'hello', 'hey']:
                        # Welcome message
                        response_message = (
                            "Hi! Welcome to Finzo, your personal refinancing assistant. 😊\n\n"
                            "Here's how I can help you:\n"
                            "- Get an estimation of your potential savings.\n"
                            "- Provide personalized guidance for refinancing.\n\n"
                            "Let's start by getting your name. Please share your name to proceed."
                        )
                        send_whatsapp_message(phone_number, response_message)
                    
                    elif is_name(user_message):  
                        # If the message is likely a name
                        response_message = (
                            f"Nice to meet you, {user_message.capitalize()}! 😊\n"
                            "How old are you? (Must be between 18 and 70)"
                        )
                        send_whatsapp_message(phone_number, response_message)
                    
                    else:
                        # Fallback message for unrecognized input
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
    """
    Send a message to the user via WhatsApp using the Meta API.
    """
    import requests
    try:
        url = f"https://graph.facebook.com/v17.0/{os.getenv('WHATSAPP_PHONE_ID')}/messages"
        headers = {
            'Authorization': f'Bearer {os.getenv("WHATSAPP_API_TOKEN")}',
            'Content-Type': 'application/json'
        }
        payload = {
            'messaging_product': 'whatsapp',
            'to': phone_number,
            'type': 'text',
            'text': {'body': message}
        }
        logging.info(f"📤 Sending message to {phone_number}: {message}")
        response = requests.post(url, json=payload, headers=headers)
        
        if response.status_code == 200:
            logging.info(f"✅ Message sent successfully to {phone_number}")
        else:
            logging.error(f"❌ Failed to send message to {phone_number}. Response: {response.json()}")
    except Exception as e:
        logging.error(f"❌ Error sending message to {phone_number}: {e}")

def is_name(text):
    """
    Check if the text is likely a name.
    Simple logic: Check if it's alphabetic and contains at most 2 words.
    """
    if len(text.split()) <= 2 and text.replace(" ", "").isalpha():
        return True
    return False

# This is a dummy change to trigger Heroku deployment
