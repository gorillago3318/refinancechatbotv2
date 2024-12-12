import os
import logging
from flask import Flask, request
from backend.routes.chatbot import chatbot_bp  # Updated import path for chatbot Blueprint

# Configure logging to ensure all logs are captured
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def create_app():
    """Create the Flask application."""
    app = Flask(__name__)
    register_routes(app)
    return app

def register_routes(app):
    """Register all routes for the application."""
    
    # Attach the chatbot blueprint for handling the main chatbot flow
    app.register_blueprint(chatbot_bp, url_prefix='/chatbot')
    
    @app.route('/webhook', methods=['GET', 'POST'])
    def webhook():
        """Handles the webhook requests from WhatsApp."""
        if request.method == 'POST':
            try:
                data = request.json
                logging.info(f"📩 Full request payload: {data}")  # Log full request payload for debugging

                # Extract message data properly
                entry = data.get('entry', [])
                if not entry:
                    logging.warning(f"⚠️ No entry found in request payload.")
                    return 'OK', 200

                change = entry[0].get('changes', [])
                if not change:
                    logging.warning(f"⚠️ No changes found in request payload.")
                    return 'OK', 200

                value = change[0].get('value', {})
                messages = value.get('messages', [])

                if messages:
                    message = messages[0]  # Get the first message in the array
                    phone_number = message.get('from')
                    user_message = message.get('text', {}).get('body', '').strip()  # Extract the actual message body

                    if phone_number and user_message:
                        logging.info(f"💎 Incoming message from {phone_number}: {user_message}")
                        
                        # Redirect request to chatbot flow via the chatbot blueprint route
                        from flask import current_app  # Avoid circular imports
                        with current_app.test_request_context('/chatbot/process_message', json={"phone_number": phone_number, "message": user_message}):
                            response = current_app.view_functions['chatbot.process_message']()
                            return response
                    else:
                        logging.warning(f"⚠️ Message data is incomplete. Phone: {phone_number}, Message: {user_message}")
                else:
                    logging.info(f"⚠️ No 'messages' key in the request. This could be a status update (e.g., delivered, read).")

            except Exception as e:
                logging.error(f"❌ Error while processing the webhook: {e}", exc_info=True)
        return 'OK', 200
