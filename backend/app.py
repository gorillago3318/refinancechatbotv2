import os
import logging
from flask import Flask, request, jsonify  
from dotenv import load_dotenv  
from backend.extensions import db, migrate  
from backend.models import User, Lead, ChatLog, BankRate  
from backend.routes.chatbot import chatbot_bp  
from backend.utils.whatsapp import send_whatsapp_message  
from backend.config import configurations

# Configure logging
logging.basicConfig(level=logging.INFO)

# Load environment variables from .env file
load_dotenv()

def create_app():
    """Create and configure the Flask app."""
    app = Flask(__name__)  # ✅ Initialize the Flask app at the top

    # Setup database config
    database_url = os.getenv('DATABASE_URL', 'sqlite:///local.db')
    if database_url.startswith('postgres://'):
        database_url = database_url.replace('postgres://', 'postgresql://', 1)
    app.config['SQLALCHEMY_DATABASE_URI'] = database_url  # ✅ Database URL
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    # Initialize database and migration tools
    db.init_app(app)
    migrate.init_app(app, db)

    # Register routes (blueprints)
    register_routes(app)

    return app  # ✅ Make sure to return the app here


def register_routes(app):
    """Register all routes for the application."""
    app.register_blueprint(chatbot_bp, url_prefix='/chatbot')  # Attach the chatbot blueprint
    
    @app.route('/webhook', methods=['GET', 'POST'])
    def webhook():
        """Handles the webhook requests from WhatsApp."""
        
        if request.method == 'GET':
            mode = request.args.get('hub.mode')
            token = request.args.get('hub.verify_token')
            challenge = request.args.get('hub.challenge')

            if mode == 'subscribe' and token == os.getenv('VERIFY_TOKEN', 'myverifytoken123'):
                logging.info('✅ Webhook verification successful!')
                return challenge, 200
            else:
                logging.warning('⚠️ Webhook verification failed! Check the token and URL.')
                return 'Verification failed', 403

        if request.method == 'POST':
            try:
                data = request.get_json() 
                logging.info(f"📩 Full request payload: {data}")  

                entries = data.get('entry', [])
                if not entries:
                    logging.warning("⚠️ No 'entry' found in request payload. Skipping processing.")
                    return 'OK', 200

                response = None  # Ensure response is always defined
                for entry in entries:
                    changes = entry.get('changes', [])
                    for change in changes:
                        value = change.get('value', {})
                        messages = value.get('messages', [])
                        if not messages:
                            logging.info("⚠️ No 'messages' in the payload. It may be a status update.")
                            continue

                        for message in messages:
                            phone_number = message.get('from', 'Unknown')
                            user_message = message.get('text', {}).get('body', 'No message body').strip()
                            logging.info(f"💎 Incoming message from {phone_number}: {user_message}")
                            
                            try:
                                with app.app_context():  
                                    response = app.view_functions['chatbot.process_message']()
                            except KeyError as e:
                                logging.error(f"❌ Route 'chatbot.process_message' not found. Check your blueprint configuration. Error: {e}")
                                response = None

                if response and isinstance(response, tuple):  
                    response = response[0]  
                    return response

            except KeyError as e:
                logging.error(f"❌ KeyError while processing webhook: {e}")
                return 'OK', 200
            except Exception as e:
                logging.exception(f"❌ Error occurred while processing webhook: {e}")
                return 'Internal Server Error', 500

        return 'OK', 200
    
    # Print environment variables for debugging purposes
    print("WHATSAPP_API_URL:", os.getenv('WHATSAPP_API_URL'))
    print("WHATSAPP_API_TOKEN:", os.getenv('WHATSAPP_API_TOKEN'))
    print("WHATSAPP_PHONE_NUMBER_ID:", os.getenv('WHATSAPP_PHONE_NUMBER_ID'))


# ✅ Expose the app globally so gunicorn can find it
app = create_app()

if __name__ == '__main__':
    app.run(debug=True, port=5000)
