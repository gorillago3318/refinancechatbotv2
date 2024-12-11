import os
from flask import Blueprint, request, jsonify
from backend.helpers import get_lead, update_lead_state, reset_lead_state
from backend.utils.whatsapp import send_whatsapp_message, send_message_to_admin
from backend.extensions import db
import json
import logging
import re
from backend.utils.calculation import calculate_savings, format_years_saved, find_best_bank_rate, extract_number
from backend.models import Lead, BankRate
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
    data = req.get_json()
    
    try:
        entry = data['entry'][0]
        changes = entry['changes'][0]
        value = changes['value']
        messages = value.get('messages', [])

        if not messages:
            return jsonify({"status": "no messages"}), 200

        message = messages[0]
        from_number = message['from']
        text = message.get('text', {}).get('body', '').strip().lower()
    except (KeyError, IndexError) as e:
        return jsonify({"error": "Invalid payload"}), 400

    # Check for "restart" command
    if text == 'restart':
        reset_lead_state(from_number)
        send_whatsapp_message(from_number, "🔄 Restarting your session. Let's start fresh.\n\nFirst, may I have your name?")
        return jsonify({"status": "session restarted"}), 200
    
    lead = get_lead(from_number)
    current_time = datetime.utcnow()
    
    if lead and lead.updated_at < current_time - timedelta(minutes=SESSION_TIMEOUT_MINUTES):
        reset_lead_state(from_number)
        send_whatsapp_message(from_number, "⏳ Your session has expired due to inactivity. Let's start again from the beginning.")
        return jsonify({"status": "session expired"}), 200
    
    if not lead or lead.conversation_state == 'end':
        lead = Lead(phone_number=from_number)
        db.session.add(lead)
        db.session.commit()
        
        welcome_msg = (
            "💡 Welcome to FinZo!\n\n" 
            "I'm FinZo, your AI Refinancing Assistant. I'll guide you through the refinancing process " 
            "and provide a detailed, accurate report based on your loan details.\n\n"
            "At any time, you may type 'restart' to start over.\n\n"
            "First, may I have your name?"
        )
        send_whatsapp_message(from_number, welcome_msg)
        update_lead_state(lead, 'get_name')
        return jsonify({"status": "conversation started"}), 200

    state = lead.conversation_state
    lead.updated_at = current_time
    db.session.commit()
    
    if state == 'get_name':
        lead.name = text
        update_lead_state(lead, 'get_age')
        send_whatsapp_message(from_number, "Thank you, {}!\nPlease provide your age.\n\n💡 Guide: Your age must be between 18 and 70.".format(text))
        return jsonify({"status": "name captured"}), 200
    
    elif state == 'get_age':
        if text.isdigit() and 18 <= int(text) <= 70:
            lead.age = int(text)
            update_lead_state(lead, 'get_loan_amount')
            send_whatsapp_message(from_number, "Please provide your original loan amount.\n\n💡 Guide: Enter in one of these formats: 200k, 200,000, or RM200,000.")
        else:
            send_whatsapp_message(from_number, "Invalid age. Please enter a valid age (between 18 and 70).")
        return jsonify({"status": "age captured"}), 200
    
    elif state == 'get_loan_amount':
        amount = extract_number(text)
        if amount:
            lead.original_loan_amount = amount
            update_lead_state(lead, 'get_tenure')
            send_whatsapp_message(from_number, "Next, provide the original loan tenure in years approved for your loan.\n\n💡 Guide: Enter the tenure as a whole number (e.g., 30).")
        else:
            send_whatsapp_message(from_number, "Invalid amount. Please provide a valid loan amount (e.g., 200k, 200,000, or RM200,000).")
        return jsonify({"status": "loan amount captured"}), 200
    
    elif state == 'get_tenure':
        if text.isdigit():
            lead.original_loan_tenure = int(text)
            update_lead_state(lead, 'get_repayment')
            send_whatsapp_message(from_number, "Please provide your current monthly repayment.\n\n💡 Guide: Enter in one of these formats: 1.2k, 1,200, or RM1,200.")
        else:
            send_whatsapp_message(from_number, "Invalid tenure. Please enter the tenure as a whole number (e.g., 30).")
        return jsonify({"status": "tenure captured"}), 200
