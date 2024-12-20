import os
import logging
from flask import Flask, request, current_app, jsonify  
from dotenv import load_dotenv  
from backend.extensions import db, migrate  
from backend.models import User, Lead, ChatLog, BankRate  
from backend.routes.chatbot import chatbot_bp  
from backend.utils.whatsapp import send_whatsapp_message  

# Configure logging
logging.basicConfig(level=logging.INFO)

# Load environment variables
load_dotenv()

def create_app():
    """Create and configure the Flask app."""
    app = Flask(__name__)

    # Setup database config
    app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///local.db')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    # Initialize database and migrate
    db.init_app(app)  
    migrate.init_app(app, db)  

    # Register all blueprints
    register_routes(app)

    return app

def register_routes(app):
    """Register all routes for the application."""
    app.register_blueprint(chatbot_bp, url_prefix='/chatbot')  
    
    @app.route('/webhook', methods=['GET', 'POST'])
    def webhook():
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
                entries = data.get('entry', [])
                for entry in entries:
                    changes = entry.get('changes', [])
                    for change in changes:
                        value = change.get('value', {})
                        messages = value.get('messages', [])
                        for message in messages:
                            phone_number = message.get('from', 'Unknown')
                            user_message = message.get('text', {}).get('body', 'No message body').strip()
                            logging.info(f"💎 Incoming message from {phone_number}: {user_message}")
                            
                            with current_app.app_context():  
                                response = current_app.view_functions['chatbot.process_message']()
                return 'OK', 200

            except Exception as e:
                logging.exception(f"❌ Error occurred while processing webhook: {e}")
                return 'Internal Server Error', 500

    print("WHATSAPP_API_URL:", os.getenv('WHATSAPP_API_URL'))
    print("WHATSAPP_API_TOKEN:", os.getenv('WHATSAPP_API_TOKEN'))
    print("WHATSAPP_PHONE_NUMBER_ID:", os.getenv('WHATSAPP_PHONE_NUMBER_ID'))

if __name__ == '__main__':
    app = create_app()
    app.run(debug=True, port=5000)
