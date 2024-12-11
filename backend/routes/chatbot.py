import os
import logging
from flask import Blueprint, request, jsonify
from backend.helpers import get_lead, update_lead_state, reset_lead_state
from backend.utils.whatsapp import send_whatsapp_message
from backend.extensions import db
from backend.utils.calculation import calculate_savings, extract_number
from backend.models import Lead
from datetime import datetime, timedelta

chatbot_bp = Blueprint('chatbot', __name__)
logger = logging.getLogger(__name__)

SESSION_TIMEOUT_MINUTES = 5  # Session timeout after 5 minutes of inactivity

@chatbot_bp.route('/webhook', methods=['GET', 'POST'])
def whatsapp_webhook():
    if request.method == 'GET':
        return verify_webhook(request)
    elif request.method == 'POST':
        return handle_incoming_message(request)
    else:
        return jsonify({"error": "Method not allowed"}), 405

def verify_webhook(req):
    verify_token = os.getenv('WHATSAPP_VERIFY_TOKEN')
    mode = req.args.get('hub.mode')
    token = req.args.get('hub.verify_token')
    challenge = req.args.get('hub.challenge')
    
    if mode and token:
        if mode == 'subscribe' and token == verify_token:
            return challenge, 200
        else:
            return 'Verification token mismatch', 403
    return 'Hello World', 200

def handle_incoming_message(req):
    try:
        data = req.get_json()
        entry = data.get('entry', [{}])[0]
        changes = entry.get('changes', [{}])[0]
        value = changes.get('value', {})
        messages = value.get('messages', [])
        
        if not messages:
            logging.info(f"No messages found in the webhook payload: {data}")
            return jsonify({"status": "no messages"}), 200
        
        message = messages[0]
        from_number = message.get('from')
        text = message.get('text', {}).get('body', '').strip().lower()
        
        logging.info(f"Incoming message from {from_number}: {text}")
        
        # Restart logic
        if text == 'restart':
            try:
                reset_lead_state(from_number)
                send_whatsapp_message(from_number, "🔄 Restarting your session. Let's start fresh.\n\nFirst, may I have your name?")
            except Exception as e:
                logging.error(f"Failed to reset lead state for {from_number}: {e}")
                send_whatsapp_message(from_number, "❌ Failed to restart. Please try again later.")
            return jsonify({"status": "session restarted"}), 200
        
        lead = get_lead(from_number)
        if lead and lead.updated_at < datetime.utcnow() - timedelta(minutes=SESSION_TIMEOUT_MINUTES):
            reset_lead_state(from_number)
            send_whatsapp_message(from_number, "⏳ Your session has expired due to inactivity. Let's start again from the beginning.")
            return jsonify({"status": "session expired"}), 200

        if not lead or lead.conversation_state == 'end':
            lead = Lead(phone_number=from_number)
            db.session.add(lead)
            db.session.commit()
            
            send_whatsapp_message(from_number, "💡 Welcome to FinZo!\n\nMay I have your name?")
            update_lead_state(lead, 'get_name')
            return jsonify({"status": "conversation started"}), 200

        # Process user response based on conversation state
        return handle_user_response(lead.conversation_state, text, lead, from_number)

    except Exception as e:
        logging.error(f"Error handling incoming message: {e}")
        return jsonify({"error": "Internal server error"}), 500

def handle_user_response(state, text, lead, from_number):
    try:
        if state == 'get_name':
            lead.name = text
            update_lead_state(lead, 'get_age')
            send_whatsapp_message(from_number, "Thanks, {}! Please provide your age (18-70).".format(text))

        elif state == 'get_age':
            if text.isdigit() and 18 <= int(text) <= 70:
                lead.age = int(text)
                update_lead_state(lead, 'get_loan_amount')
                send_whatsapp_message(from_number, "Great! Please provide your original loan amount.")
            else:
                send_whatsapp_message(from_number, "Please provide a valid age (18-70).")

        elif state == 'get_loan_amount':
            amount = extract_number(text)
            if amount:
                lead.original_loan_amount = amount
                update_lead_state(lead, 'get_tenure')
                send_whatsapp_message(from_number, "Next, provide the original loan tenure in years.")
            else:
                send_whatsapp_message(from_number, "Please provide a valid loan amount.")

        elif state == 'get_tenure':
            if text.isdigit():
                lead.original_loan_tenure = int(text)
                update_lead_state(lead, 'get_repayment')
                send_whatsapp_message(from_number, "Please provide your current monthly repayment.")
            else:
                send_whatsapp_message(from_number, "Please provide the tenure in whole years.")
    except Exception as e:
        logging.error(f"Error processing user response: {e}")
