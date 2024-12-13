import os
import logging
from flask import Flask, request, current_app
from .extensions import db, migrate  # Import the extensions from extensions.py
from backend.routes.chatbot import chatbot_bp  # Import the chatbot Blueprint

# Configure logging
logging.basicConfig(level=logging.INFO)

def create_app():
    """Create and configure the Flask app."""
    app = Flask(__name__)

    # Setup database config
    app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://username:password@localhost:5432/dbname'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    # Initialize database and migrate
    db.init_app(app)  
    migrate.init_app(app, db)  

    # Register all blueprints
    register_routes(app)

    return app
def register_routes(app):
    """Register all routes for the application."""
    # Attach the chatbot blueprint for handling the main flow
    app.register_blueprint(chatbot_bp, url_prefix='/chatbot')
    
    @app.route('/webhook', methods=['GET', 'POST'])
    def webhook():
        """Handles the webhook requests from WhatsApp."""
        if request.method == 'POST':
            try:
                data = request.get_json()  # Ensure get_json() is used properly
                logging.info(f"📩 Full request payload: {data}")  # Log full request payload for debugging

                # Extract message data
                entry = data.get('entry', [{}])[0]
                changes = entry.get('changes', [{}])[0]
                value = changes.get('value', {})
                messages = value.get('messages', [])
                
                if messages:
                    message = messages[0]
                    phone_number = message.get('from')
                    user_message = message.get('text', {}).get('body', '').strip()

                    logging.info(f"💎 Incoming message from {phone_number}: {user_message}")
                    
                    # Use the process_message route instead of hardcoding 'start_chat'
                    with current_app.test_request_context('/chatbot/process_message', json={"phone_number": phone_number, "message": user_message}):
                        response = chatbot_bp.view_functions['process_message']()
                        return response
                
                else:
                    logging.warning(f"⚠️ No messages found in request data. This could be a status update or a delivery report.")
            except Exception as e:
                logging.error(f"❌ Error occurred while processing webhook: {e}")
        
        return 'OK', 200
