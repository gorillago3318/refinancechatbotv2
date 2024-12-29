import os
import logging
from flask import Flask, request, current_app, jsonify  
from dotenv import load_dotenv  
from backend.extensions import db, migrate  
from backend.models import User, Lead, ChatLog, BankRate  # Correct capitalization
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
    database_url = os.getenv('DATABASE_URL', 'sqlite:///local.db')

    # 🛠️ Fix Heroku's postgres URL if required (Heroku may still use 'postgres://')
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql+psycopg2://", 1)

    app.config['SQLALCHEMY_DATABASE_URI'] = database_url
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

                            # Pass data explicitly to chatbot
                            with current_app.app_context():  
                                response = current_app.view_functions['chatbot.process_message']()
                return 'OK', 200

            except Exception as e:
                logging.exception(f"❌ Error occurred while processing webhook: {e}")
                return 'Internal Server Error', 500

    # Print environment variables for debugging
    logging.info("WHATSAPP_API_URL: %s", os.getenv('WHATSAPP_API_URL'))
    logging.info("WHATSAPP_API_TOKEN: %s", os.getenv('WHATSAPP_API_TOKEN'))
    logging.info("WHATSAPP_PHONE_NUMBER_ID: %s", os.getenv('WHATSAPP_PHONE_NUMBER_ID'))

if __name__ == '__main__':
    DEBUG = os.getenv('DEBUG', 'False').lower() in ['true', '1', 'yes']
    app = create_app()
    app.run(debug=DEBUG, port=5000)
