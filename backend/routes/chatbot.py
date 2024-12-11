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
    
    response = handle_user_response(state, text, lead)
    send_whatsapp_message(from_number, response["message"])
    return jsonify(response)

def handle_user_response(state, user_response, lead):
    user_response = user_response.strip()

    if state == 'get_name':
        if not user_response:
            return {"status": "error", "message": "Please enter a valid name to continue."}
        lead.name = user_response
        update_lead_state(lead, 'get_age')
        return {"status": "success", "message": "Thanks! How old are you?"}

    elif state == 'get_age':
        try:
            age = int(user_response)
            if age <= 0:
                raise ValueError("Age must be greater than 0")
        except ValueError:
            return {"status": "error", "message": "Please provide a valid age as a whole number."}
        
        lead.age = age
        update_lead_state(lead, 'get_loan_amount')
        return {"status": "success", "message": "Thanks! What's your loan amount?"}

    elif state == 'get_loan_amount':
        loan_amount = extract_number(user_response)
        if not loan_amount or loan_amount <= 0:
            return {"status": "error", "message": "Please provide a valid loan amount. (e.g., 200k, 200,000, or RM200,000)"}
        
        lead.original_loan_amount = loan_amount
        update_lead_state(lead, 'get_optional_interest_rate')
        return {"status": "success", "message": "Do you know your interest rate? You can provide it or type 'skip'."}

    elif state == 'get_optional_interest_rate':
        if user_response.lower() == 'skip':
            update_lead_state(lead, 'get_optional_tenure')
            return {"status": "success", "message": "No problem! Do you know your remaining tenure? You can enter it or type 'skip'."}
        
        try:
            interest_rate = float(user_response)
            if interest_rate <= 0:
                raise ValueError("Interest rate must be positive")
        except ValueError:
            return {"status": "error", "message": "Please provide a valid interest rate or type 'skip' to continue."}
        
        lead.interest_rate = interest_rate
        update_lead_state(lead, 'get_optional_tenure')
        return {"status": "success", "message": "Got it! Do you know your remaining tenure? You can enter it or type 'skip'."}

    elif state == 'get_optional_tenure':
        if user_response.lower() == 'skip':
            update_lead_state(lead, 'final_step')
            return {"status": "success", "message": "Great! We have all the information we need. We'll process your information now."}
        
        try:
            remaining_tenure = int(user_response)
            if remaining_tenure <= 0:
                raise ValueError("Tenure must be a positive number.")
        except ValueError:
            return {"status": "error", "message": "Please provide a valid tenure in years or type 'skip' to continue."}
        
        lead.remaining_tenure = remaining_tenure
        update_lead_state(lead, 'final_step')
        return {"status": "success", "message": "Great! We have all the information we need. We'll process your information now."}

    return {"status": "error", "message": "Invalid state. Please try again or type 'restart' to start over."}
