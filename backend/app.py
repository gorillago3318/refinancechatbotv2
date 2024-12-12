import os
import logging
from flask import Flask, request, jsonify
from dotenv import load_dotenv
from backend.extensions import db, migrate  # Absolute import

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)

def create_app():
    """Application factory to create and configure the app."""
    app = Flask(__name__)
    
    # Set configuration for the app
    app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///local.db')
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'your_default_secret_key')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    
    # Register chatbot blueprint
    try:
        from backend.routes.chatbot import chatbot_bp
        app.register_blueprint(chatbot_bp, url_prefix='/api/chatbot')
        logging.info("✅ Successfully registered chatbot blueprint at /api/chatbot")
    except Exception as e:
        logging.error(f"❌ Failed to register chatbot blueprint: {e}")
    
    # **Webhook route** to receive WhatsApp messages
    @app.route('/webhook', methods=['GET', 'POST'])
    def webhook():
        """Handles verification (GET) and incoming WhatsApp messages (POST)."""
        if request.method == 'GET':
            # Step 1: Verification request from Meta
            token = request.args.get('hub.verify_token')
            challenge = request.args.get('hub.challenge')
            if token == os.getenv('VERIFY_TOKEN'):  # Custom token you set on Heroku
                logging.info("✅ Webhook verified successfully!")
                return challenge
            logging.error(f"❌ Verification failed. Token provided: {token}")
            return 'Invalid verify token', 403

        if request.method == 'POST':
            # Step 2: Handle incoming messages from WhatsApp
            try:
                data = request.get_json()  # Get the incoming JSON payload
                logging.info(f"📩 Incoming message: {data}")
                
                if 'messages' in data['entry'][0]['changes'][0]['value']:
                    message = data['entry'][0]['changes'][0]['value']['messages'][0]
                    phone_number = message['from']  # User phone number
                    user_message = message['text']['body']  # User's reply message
                    
                    logging.info(f"User {phone_number} says: {user_message}")
                    
                    # TODO: Store this message in the ChatLog table if required.
                    # Example:
                    # from backend.models import ChatLog
                    # new_chatlog = ChatLog(phone_number=phone_number, message=user_message, response='automated response here')
                    # db.session.add(new_chatlog)
                    # db.session.commit()
                    
                    return jsonify({"status": "received"}), 200
                
                logging.warning(f"⚠️ No messages found in incoming request: {data}")
                return jsonify({"status": "no messages found"}), 200
            except Exception as e:
                logging.error(f"❌ Error processing webhook request: {str(e)}")
                return jsonify({"status": "error", "message": str(e)}), 500

    return app


app = create_app()

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))  # Heroku dynamically sets the port
    app.run(host='0.0.0.0', port=port, debug=os.getenv('DEBUG', 'False').lower() == 'true')
