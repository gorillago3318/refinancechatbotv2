import os
from flask import Blueprint, request, jsonify
from backend.helpers import get_lead, update_lead_state, reset_lead_state
from backend.utils.whatsapp import send_whatsapp_message
from backend.extensions import db
import json
import logging
import re
from backend.models import Lead

chatbot_bp = Blueprint('chatbot', __name__)
logger = logging.getLogger(__name__)

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
        message = data['entry'][0]['changes'][0]['value']['messages'][0]
        from_number = message['from']
        text = message.get('text', {}).get('body', '').strip()
    except (KeyError, IndexError) as e:
        logger.error(f"Invalid payload structure: {e}")
        return jsonify({"error": "Invalid payload"}), 400

    # Check if a lead exists for this phone number
    lead = get_lead(from_number)
    if not lead:
        lead = Lead(phone_number=from_number)
        db.session.add(lead)
        db.session.commit()

    # Handle 'restart' command
    if text.lower() == 'restart':
        reset_lead_state(lead)
        send_whatsapp_message(from_number, "Conversation restarted. Please provide your Name.")
        update_lead_state(lead, 'get_name')
        return jsonify({"status": "conversation restarted"}), 200

    # Determine the current state of the user's conversation
    state = lead.conversation_state

    # 1️⃣ ASK FOR NAME
    if state == 'START' or state == 'get_name':
        if validate_name(text):
            lead.name = text.strip()
            update_lead_state(lead, 'get_loan_amount')
            db.session.commit()
            send_whatsapp_message(from_number, f"Thank you, {lead.name}! Next, please provide your original loan amount in RM (e.g., 200000).")
            return jsonify({"status": "name received"}), 200
        else:
            send_whatsapp_message(from_number, "Please provide your name (letters only).")
            return jsonify({"status": "awaiting name"}), 200

    # 2️⃣ ASK FOR LOAN AMOUNT
    elif state == 'get_loan_amount':
        loan_amount = extract_number(text)
        if loan_amount and loan_amount > 0:
            lead.original_loan_amount = loan_amount
            update_lead_state(lead, 'get_tenure')
            db.session.commit()
            send_whatsapp_message(from_number, f"Great! Your loan amount is RM {loan_amount}. Next, please provide the loan tenure in years (e.g., 30).")
            return jsonify({"status": "loan amount received"}), 200
        else:
            send_whatsapp_message(from_number, "Please enter a valid loan amount (e.g., 200000).")
            return jsonify({"status": "awaiting loan amount"}), 200

    # 3️⃣ ASK FOR LOAN TENURE
    elif state == 'get_tenure':
        tenure = extract_number(text)
        if tenure and 1 <= tenure <= 40:  # Tenure should be between 1 and 40 years
            lead.original_loan_tenure = int(tenure)
            update_lead_state(lead, 'get_repayment')
            db.session.commit()
            send_whatsapp_message(from_number, f"Got it! Your loan tenure is {tenure} years. Finally, please provide your current monthly repayment (e.g., 1200).")
            return jsonify({"status": "tenure received"}), 200
        else:
            send_whatsapp_message(from_number, "Please enter a valid tenure (between 1 and 40 years).")
            return jsonify({"status": "awaiting tenure"}), 200

    # 4️⃣ ASK FOR CURRENT MONTHLY REPAYMENT
    elif state == 'get_repayment':
        repayment = extract_number(text)
        if repayment and repayment > 0:
            lead.current_repayment = repayment
            update_lead_state(lead, 'complete')
            db.session.commit()
            send_summary_to_user(from_number, lead)
            return jsonify({"status": "repayment received"}), 200
        else:
            send_whatsapp_message(from_number, "Please enter a valid monthly repayment amount (e.g., 1200).")
            return jsonify({"status": "awaiting repayment"}), 200

    else:
        send_whatsapp_message(from_number, "I'm not sure what to do. Please type 'restart' to start over.")
        return jsonify({"status": "unknown state"}), 200


def send_summary_to_user(phone_number, lead):
    summary = (
        f"Thanks, {lead.name}! Here’s a summary of your details:\n\n"
        f"💰 Loan Amount: RM{lead.original_loan_amount}\n"
        f"📆 Tenure: {lead.original_loan_tenure} years\n"
        f"📉 Monthly Repayment: RM{lead.current_repayment}\n\n"
        "An agent will contact you shortly. If you would like to change any details, type 'restart' to start over."
    )
    send_whatsapp_message(phone_number, summary)


def validate_name(text):
    """ Checks if the text is a valid name (letters only) """
    return re.match(r'^[A-Za-z\s]+$', text)


def extract_number(text):
    """ Extracts a numeric value from the user's input """
    match = re.search(r'\d+(\.\d+)?', text)
    if match:
        return float(match.group())
    return None
