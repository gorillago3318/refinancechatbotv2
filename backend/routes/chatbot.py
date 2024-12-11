import os
from flask import Blueprint, request, jsonify
from backend.helpers import get_lead, update_lead_state, reset_lead_state
from backend.utils.whatsapp import send_whatsapp_message, send_message_to_admin
from backend.extensions import db
import json
import logging
import re
import openai
from backend.utils.calculation import calculate_savings, format_years_saved
from backend.models import Lead, BankRate

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
    logger.debug(f"Webhook verification: mode={mode}, token={token}, challenge={challenge}")

    if mode and token:
        if mode == 'subscribe' and token == verify_token:
            logger.info('WEBHOOK_VERIFIED')
            return challenge, 200
        else:
            logger.warning('WEBHOOK_VERIFICATION_FAILED: Token mismatch')
            return 'Verification token mismatch', 403
    return 'Hello World', 200

def handle_incoming_message(req):
    data = req.get_json()
    logger.debug(f"Received data: {json.dumps(data)}")

    try:
        entry = data['entry'][0]
        changes = entry['changes'][0]
        value = changes['value']
        messages = value.get('messages', [])

        if not messages:
            logger.info('No messages in this request.')
            return jsonify({"status": "no messages"}), 200

        message = messages[0]
        from_number = message['from']
        text = message.get('text', {}).get('body', '').strip()
        logger.info(f"Received message from {from_number}: {text}")
    except (KeyError, IndexError) as e:
        logger.error(f"Invalid payload structure: {e}")
        return jsonify({"error": "Invalid payload"}), 400

    # 'restart' command
    if text.lower() == 'restart':
        lead = get_lead(from_number)
        if lead:
            reset_lead_state(lead)
        else:
            lead = Lead(phone_number=from_number)
            db.session.add(lead)
            db.session.commit()

        restart_msg = (
            "Conversation restarted.\n\n"
            "Welcome to FinZo!\n\n"
            "I am FinZo, your AI Refinancing Assistant. I will guide you through the refinancing process and "
            "provide a detailed, accurate report based on your loan details.\n\n"
            "At any time, you may type 'restart' to start over.\n\n"
            "First, may I have your Name?"
        )
        send_whatsapp_message(from_number, restart_msg)
        update_lead_state(lead, 'get_name')
        return jsonify({"status": "conversation restarted"}), 200

    lead = get_lead(from_number)
    if not lead:
        lead = Lead(phone_number=from_number)
        db.session.add(lead)
        db.session.commit()
        greeting = (
            "Welcome to FinZo!\n\n"
            "I am FinZo, your AI Refinancing Assistant. I will help you understand your refinancing options and "
            "provide an accurate report based on your details.\n\n"
            "At any time, you may type 'restart' to start over.\n\n"
            "First, may I have your Name?"
        )
        send_whatsapp_message(from_number, greeting)
        update_lead_state(lead, 'get_name')
        return jsonify({"status": "greeting sent"}), 200

    state = lead.conversation_state

    if state == 'end':
        lead.question_count += 1
        db.session.commit()
        if lead.question_count > 5:
            contact_admin_prompt = (
                "It appears you have multiple questions. For further assistance, please contact our admin directly:\n\n"
                "https://wa.me/60167177813"
            )
            send_whatsapp_message(from_number, contact_admin_prompt)
            return jsonify({"status": "admin contact prompted"}), 200

        sanitized_question = sanitize_input(text)
        response = handle_user_question(sanitized_question)
        send_whatsapp_message(from_number, response)
        return jsonify({"status": "question answered"}), 200

def sanitize_input(text):
    return re.sub(r'[^\w\s,.%-]', '', text)

def extract_number(text):
    match = re.search(r'\d+(\.\d+)?', text)
    if match:
        return float(match.group())
    return None

def parse_loan_amount(text):
    t = text.lower().replace('rm', '').replace(',', '').strip()
    multiplier = 1
    if 'k' in t:
        multiplier = 1000
        t = t.replace('k', '')
    try:
        return float(t) * multiplier
    except ValueError:
        return None
