from flask import Blueprint, request, jsonify
from datetime import datetime
from ..extensions import db
from ..models import User, Lead, ChatLog, BankRate

chatbot_bp = Blueprint('chatbot', __name__)

# Helper function to send chatbot message response
def send_message(phone_number, message):
    """ Simulate sending a message (could be replaced with actual WhatsApp API) """
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
    data = request.get_json()
    phone_number = data.get('phone_number')
    message_body = data.get('message', '').strip()
    
    if message_body.lower() == 'restart':
        return restart_chat()
    
    user = User.query.filter_by(wa_id=phone_number).first()
    
    if not user or not user.current_step:
        return start_chat()
    
    current_step = user.current_step
    
    if current_step == 'get_name':
        return get_name(phone_number, message_body)
    elif current_step == 'get_age':
        return get_age(phone_number, message_body)
    elif current_step == 'get_loan_amount':
        return get_loan_amount(phone_number, message_body)
    elif current_step == 'get_loan_tenure':
        return get_loan_tenure(phone_number, message_body)
    elif current_step == 'get_monthly_repayment':
        return get_monthly_repayment(phone_number, message_body)
    else:
        return send_message(phone_number, "I'm not sure how to respond to that. You can ask me questions about refinancing, or type 'restart' to begin.")


def get_name(phone_number, name):
    """Get user name and ask for their age"""
    if not name or name.lower() == 'restart':
        return restart_chat()
    
    user = User.query.filter_by(wa_id=phone_number).first()
    if not user:
        user = User(wa_id=phone_number, name=name, current_step='get_age')
        db.session.add(user)
    else:
        user.name = name
        user.current_step = 'get_age'
    
    db.session.commit()
    return send_message(phone_number, f"Thanks, {name}! How old are you? (18-70)")


def get_age(phone_number, age):
    """Get user age and ask for current loan amount"""
    if not age.isdigit() or not (18 <= int(age) <= 70):
        return send_message(phone_number, "Please provide a valid age between 18 and 70.")
    
    user = User.query.filter_by(wa_id=phone_number).first()
    if user:
        user.age = int(age)
        user.current_step = 'get_loan_amount'
        db.session.commit()
    
    return send_message(phone_number, "Great! What's your original loan amount? (e.g., 100k, 1.2m)")


def get_loan_amount(phone_number, loan_amount):
    """Get original loan amount and ask for loan tenure"""
    try:
        if 'k' in loan_amount:
            loan_amount = float(loan_amount.replace('k', '')) * 1000
        elif 'm' in loan_amount:
            loan_amount = float(loan_amount.replace('m', '')) * 1_000_000
        else:
            loan_amount = float(loan_amount)
    except ValueError:
        return send_message(phone_number, "Please provide the loan amount in a valid format (e.g., 100k, 1.2m).")
    
    lead = Lead.query.filter_by(phone_number=phone_number).first()
    if not lead:
        lead = Lead(phone_number=phone_number, original_loan_amount=loan_amount)
        db.session.add(lead)
    else:
        lead.original_loan_amount = loan_amount
    
    user = User.query.filter_by(wa_id=phone_number).first()
    if user:
        user.current_step = 'get_loan_tenure'
    
    db.session.commit()
    return send_message(phone_number, "Thanks! What was the original loan tenure in years? (1-40)")


def get_loan_tenure(phone_number, tenure):
    """Get original loan tenure and ask for current monthly repayment"""
    if not tenure.isdigit() or not (1 <= int(tenure) <= 40):
        return send_message(phone_number, "Please provide a valid loan tenure (1-40 years).")
    
    lead = Lead.query.filter_by(phone_number=phone_number).first()
    if lead:
        lead.original_loan_tenure = int(tenure)
    
    user = User.query.filter_by(wa_id=phone_number).first()
    if user:
        user.current_step = 'get_monthly_repayment'
    
    db.session.commit()
    return send_message(phone_number, "How much is your current monthly repayment? (e.g., 1.2k)")


def get_monthly_repayment(phone_number, repayment):
    try:
        if 'k' in repayment:
            repayment = float(repayment.replace('k', '')) * 1000
        else:
            repayment = float(repayment)
    except ValueError:
        return send_message(phone_number, "Please provide the monthly repayment amount in a valid format (e.g., 1.2k).")
    
    lead = Lead.query.filter_by(phone_number=phone_number).first()
    if lead:
        lead.current_repayment = repayment
        db.session.commit()
    
    return send_message(phone_number, "If you know your existing housing loan's interest rate, please enter it. Otherwise, type 'skip'.")
