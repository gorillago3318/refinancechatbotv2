import logging
from flask import Blueprint, request, jsonify
from datetime import datetime
from ..extensions import db
from ..models import User, Lead, ChatLog, BankRate
from ..utils.calculation import perform_calculation  # Import the calculation module

chatbot_bp = Blueprint('chatbot', __name__)

# Helper function to send chatbot message response
def send_message(phone_number, message):
    """Simulate sending a message (could be replaced with actual WhatsApp API)"""
    logging.info(f"📤 Sending message to {phone_number}: {message}")
    return jsonify({"phone_number": phone_number, "message": message})

@chatbot_bp.route('/start', methods=['POST'])
def start_chat():
    """Welcome message for the user and ask for their name"""
    phone_number = request.json.get('phone_number')
    user = User.query.filter_by(wa_id=phone_number).first()

    if not user:
        user = User(wa_id=phone_number, current_step='get_name')
        db.session.add(user)
    else:
        user.current_step = 'get_name'
    
    db.session.commit()
    
    message = (
        "Hi! Welcome to FinZo, your personal refinancing assistant. 😊\n"
        "Here's how I can help you:\n"
        "- Get an estimation of your potential savings.\n"
        "- Provide personalized guidance for refinancing.\n"
        "\nLet's start by getting your name. Please share your name to proceed.\n"
        "If you make a mistake, you can type 'restart' at any time to start over."
    )
    return send_message(phone_number, message)

@chatbot_bp.route('/restart', methods=['POST'])
def restart_chat():
    """Restart the conversation by clearing user data and sending the welcome message"""
    phone_number = request.json.get('phone_number')
    User.query.filter_by(wa_id=phone_number).delete()
    Lead.query.filter_by(phone_number=phone_number).delete()
    db.session.commit()
    return start_chat()

@chatbot_bp.route('/process_message', methods=['POST'])
def process_message():
    """Process all incoming messages and route them based on current step"""
    try:
        data = request.get_json()
        phone_number = data.get('phone_number')
        message_body = data.get('message', '').strip()
        
        logging.info(f"📨 Incoming message from {phone_number}: {message_body}")
        
        if message_body.lower() == 'restart':
            return restart_chat()
        
        user = User.query.filter_by(wa_id=phone_number).first()
        if not user or not user.current_step:
            logging.info("🔄 User not found or no current step, restarting the flow.")
            return start_chat()
        
        current_step = user.current_step
        step_info = STEP_CONFIG.get(current_step)
        
        if not step_info:
            logging.warning(f"⚠️ No step configuration found for current step: {current_step}")
            return send_message(phone_number, "I'm not sure how to respond to that. You can ask me questions about refinancing, or type 'restart' to begin.")
        
        if not step_info['validator'](message_body):
            return send_message(phone_number, f"Invalid input. {step_info['message']}")
        
        # Save the user input to the relevant column
        process_user_input(current_step, phone_number, message_body)
        
        # Move to the next step
        user.current_step = step_info['next_step']
        db.session.commit()
        
        # If all steps are complete, calculate and send final message
        if user.current_step is None:
            lead = Lead.query.filter_by(phone_number=phone_number).first()
            if lead:
                result = perform_calculation(lead)  # Call the perform_calculation function
                return send_message(phone_number, result)
        
        next_message = STEP_CONFIG[user.current_step]['message'] if user.current_step else "Thank you for completing the process."
        return send_message(phone_number, next_message)
    
    except Exception as e:
        logging.error(f"❌ Error occurred in process_message: {e}")
        return send_message(data.get('phone_number'), "An unexpected error occurred. Please type 'restart' to try again.")

def process_user_input(current_step, phone_number, message_body):
    """Processes and stores user input in the database."""
    user = User.query.filter_by(wa_id=phone_number).first()
    lead = Lead.query.filter_by(phone_number=phone_number).first() or Lead(phone_number=phone_number)
    
    if current_step == 'get_name':
        user.name = message_body
    elif current_step == 'get_age':
        user.age = int(message_body)
    elif current_step == 'get_loan_amount':
        amount = parse_loan_amount(message_body)
        lead.original_loan_amount = amount
    elif current_step == 'get_loan_tenure':
        lead.original_loan_tenure = int(message_body)
    elif current_step == 'get_monthly_repayment':
        repayment = parse_loan_amount(message_body)
        lead.current_repayment = repayment
    elif current_step == 'get_interest_rate' and message_body.lower() != 'skip':
        lead.interest_rate = float(message_body)
    elif current_step == 'get_remaining_tenure' and message_body.lower() != 'skip':
        lead.remaining_tenure = int(message_body)
    
    db.session.add(lead)
    db.session.commit()

STEP_CONFIG = {
    'get_name': {
        'message': "Please share your name to proceed.",
        'next_step': 'get_age',
        'validator': lambda x: len(x) > 0
    },
    'get_age': {
        'message': "How old are you? (18-70)",
        'next_step': 'get_loan_amount',
        'validator': lambda x: x.isdigit() and 18 <= int(x) <= 70
    },
    'get_loan_amount': {
        'message': "What is your original loan amount? (e.g., 100k, 1.2m)",
        'next_step': 'get_loan_tenure',
        'validator': lambda x: x.replace('k', '').replace('m', '').replace('.', '').isdigit()
    },
    'get_loan_tenure': {
        'message': "What is the original loan tenure in years? (1-40)",
        'next_step': 'get_monthly_repayment',
        'validator': lambda x: x.isdigit() and 1 <= int(x) <= 40
    },
    'get_monthly_repayment': {
        'message': "How much is your current monthly repayment? (e.g., 1.2k)",
        'next_step': 'get_interest_rate',
        'validator': lambda x: x.replace('k', '').replace('.', '').isdigit()
    },
    'get_interest_rate': {
        'message': "Do you know your current loan's interest rate? (e.g., 3.85) or type 'skip'.",
        'next_step': 'get_remaining_tenure',
        'validator': lambda x: x.lower() == 'skip' or x.replace('.', '').isdigit()
    },
    'get_remaining_tenure': {
        'message': "How many years are left on your current loan? (e.g., 10) or type 'skip'.",
        'next_step': None,
        'validator': lambda x: x.lower() == 'skip' or (x.isdigit() and int(x) > 0)
    }
}

def parse_loan_amount(amount_str):
    """Parses loan amounts from formats like 100k, 1.2m to numeric values"""
    try:
        if 'k' in amount_str:
            return float(amount_str.replace('k', '')) * 1000
        elif 'm' in amount_str:
            return float(amount_str.replace('m', '')) * 1_000_000
        else:
            return float(amount_str)
    except ValueError:
        logging.error(f"❌ Error parsing loan amount: {amount_str}")
        return 0
