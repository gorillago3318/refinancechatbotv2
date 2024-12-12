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
                value = data.get('entry', [{}])[0].get('changes', [{}])[0].get('value', {})
                messages = value.get('messages', [])
                if messages:
                    message = messages[0]
                    phone_number = message.get('from')
                    user_message = message.get('text', {}).get('body', '').lower()
                    send_whatsapp_message(phone_number, f"Hello! You said: {user_message}")
                else:
                    logging.warning(f"⚠️ No messages found in request data.")
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
    requests.post(url, json=payload, headers=headers)
