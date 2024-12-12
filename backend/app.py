import os
import logging
from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize the database globally
db = SQLAlchemy()

# Configure logging
logging.basicConfig(level=logging.INFO)

def create_app():
    """
    Application Factory to create and configure the Flask app.
    """
    app = Flask(__name__)
    
    # Get the DATABASE_URL from environment variables
    database_url = os.getenv('DATABASE_URL', '')
    
    # Replace postgres:// with postgresql:// for compatibility
    if database_url.startswith('postgres://'):
        database_url = database_url.replace('postgres://', 'postgresql://', 1)
    
    # Flask SQLAlchemy config
    app.config['SQLALCHEMY_DATABASE_URI'] = database_url
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    # Initialize extensions
    db.init_app(app)
    
    # Register routes
    register_routes(app)
    
    return app

def register_routes(app):
    """
    Registers the routes for the app.
    """
    @app.route('/webhook', methods=['GET', 'POST'])
    def webhook():
        if request.method == 'GET':
            # Step 1: Verification request from Meta
            token = request.args.get('hub.verify_token')
            challenge = request.args.get('hub.challenge')
            if token == os.getenv('VERIFY_TOKEN'):  # Custom token you set on Heroku
                logging.info("✅ Webhook verified successfully!")
                return challenge
            return 'Invalid verify token', 403
        
        if request.method == 'POST':
            try:
                # Step 2: Handle incoming messages from WhatsApp
                data = request.json  # Get the incoming JSON payload
                logging.info(f"📩 Incoming message: {data}")
                
                if 'messages' in data['entry'][0]['changes'][0]['value']:
                    message = data['entry'][0]['changes'][0]['value']['messages'][0]
                    phone_number = message['from']  # User phone number
                    user_message = message['text']['body'].lower()  # User's message (convert to lowercase)
                    
                    logging.info(f"User {phone_number} says: {user_message}")
    
                    # **Logic to handle responses**
                    if user_message in ['hi', 'hello', 'hey']:
                        # **Welcome message**
                        response_message = (
                            "Hi! Welcome to Finzo, your personal refinancing assistant.\n\n"
                            "Here's how I can help you:\n"
                            "- Get an estimation of your potential savings.\n"
                            "- Provide personalized guidance for refinancing.\n\n"
                            "Let's start by getting your name. Please share your name to proceed."
                        )
                        send_whatsapp_message(phone_number, response_message)
    
                    elif is_name(user_message):  # If the message is a name (custom logic)
                        response_message = (
                            f"Nice to meet you, {user_message.capitalize()}! 😊\n"
                            "How old are you? (Must be between 18 and 70)"
                        )
                        send_whatsapp_message(phone_number, response_message)
                    
                    else:
                        # If message doesn't match any criteria, offer guidance
                        response_message = (
                            "I'm not sure how to respond to that.\n"
                            "You can ask me questions about refinancing, or type 'start' to begin."
                        )
                        send_whatsapp_message(phone_number, response_message)
    
                    return jsonify({"status": "message received"}), 200
                
                logging.warning(f"⚠️ No messages found in incoming request: {data}")
                return jsonify({"status": "no messages found"}), 200
            except Exception as e:
                logging.error(f"❌ Error processing webhook: {e}")
                return jsonify({"status": "error", "error": str(e)}), 500

def send_whatsapp_message(phone_number, message):
    """
    Send a message back to the user on WhatsApp using the Meta API.
    """
    import requests

    whatsapp_url = f"https://graph.facebook.com/v17.0/{os.getenv('WHATSAPP_PHONE_ID')}/messages"
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {os.getenv("WHATSAPP_API_TOKEN")}'
    }
    payload = {
        'messaging_product': 'whatsapp',
        'to': phone_number,
        'type': 'text',
        'text': {'body': message}
    }

    try:
        response = requests.post(whatsapp_url, json=payload, headers=headers)
        if response.status_code == 200:
            logging.info(f"✅ Successfully sent message to {phone_number}")
        else:
            logging.error(f"❌ Failed to send message to {phone_number}. Response: {response.json()}")
    except Exception as e:
        logging.error(f"❌ Error sending message to {phone_number}: {e}")

def is_name(text):
    """
    Check if the user message is likely a name.
    Simple logic: Check if it's alphabetic and at most 2 words.
    """
    if len(text.split()) <= 2 and text.replace(" ", "").isalpha():
        return True
    return False

if __name__ == "__main__":
    app = create_app()
    app.run(port=5000, debug=True)
