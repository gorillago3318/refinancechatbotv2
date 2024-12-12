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

@chatbot_bp.route('/get_name', methods=['POST'])
def get_name():
    """Get user name and ask for their age"""
    data = request.get_json()
    phone_number = data.get('phone_number')
    name = data.get('name')
    if not name:
        return send_message(phone_number, "Please provide your name to continue.")
    
    if name.lower() == 'restart':
        return restart_chat()
    
    user = User.query.filter_by(wa_id=phone_number).first()
    if not user:
        user = User(wa_id=phone_number, name=name)
        db.session.add(user)
    else:
        user.name = name
    
    user.current_step = 'get_age'
    db.session.commit()
    
    return send_message(phone_number, f"Thanks, {name}! How old are you? (18-70)")

@chatbot_bp.route('/get_age', methods=['POST'])
def get_age():
    """Get user age and ask for current loan amount"""
    data = request.get_json()
    phone_number = data.get('phone_number')
    age = data.get('age')
    if not age or not (18 <= int(age) <= 70):
        return send_message(phone_number, "Please provide a valid age between 18 and 70.")
    
    if str(age).lower() == 'restart':
        return restart_chat()
    
    user = User.query.filter_by(wa_id=phone_number).first()
    if user:
        user.age = age
        db.session.commit()
    
    return send_message(phone_number, "Great! What's your original loan amount? (e.g., 100k, 1.2m)")

@chatbot_bp.route('/get_loan_amount', methods=['POST'])
def get_loan_amount():
    """Get original loan amount and ask for loan tenure"""
    data = request.get_json()
    phone_number = data.get('phone_number')
    loan_amount = data.get('loan_amount')
    
    if not loan_amount:
        return send_message(phone_number, "Please provide the loan amount in a valid format (e.g., 100k, 1.2m).")
    
    if loan_amount.lower() == 'restart':
        return restart_chat()
    
    if 'k' in loan_amount:
        loan_amount = float(loan_amount.replace('k', '')) * 1000
    elif 'm' in loan_amount:
        loan_amount = float(loan_amount.replace('m', '')) * 1_000_000
    else:
        loan_amount = float(loan_amount)
    
    lead = Lead.query.filter_by(phone_number=phone_number).first()
    if not lead:
        lead = Lead(phone_number=phone_number, original_loan_amount=loan_amount)
        db.session.add(lead)
    else:
        lead.original_loan_amount = loan_amount
    
    db.session.commit()
    return send_message(phone_number, "Thanks! What was the original loan tenure in years? (1-40)")

@chatbot_bp.route('/get_loan_tenure', methods=['POST'])
def get_loan_tenure():
    """Get original loan tenure and ask for current monthly repayment"""
    data = request.get_json()
    phone_number = data.get('phone_number')
    tenure = data.get('tenure')
    
    if not tenure or not (1 <= int(tenure) <= 40):
        return send_message(phone_number, "Please provide a valid loan tenure (1-40 years).")
    
    if str(tenure).lower() == 'restart':
        return restart_chat()
    
    lead = Lead.query.filter_by(phone_number=phone_number).first()
    if lead:
        lead.original_loan_tenure = tenure
        db.session.commit()
    
    return send_message(phone_number, "How much is your current monthly repayment? (e.g., 1.2k)")

@chatbot_bp.route('/get_monthly_repayment', methods=['POST'])
def get_monthly_repayment():
    """Get monthly repayment and calculate savings"""
    data = request.get_json()
    phone_number = data.get('phone_number')
    repayment = data.get('repayment')
    
    if not repayment:
        return send_message(phone_number, "Please provide the monthly repayment amount in a valid format (e.g., 1.2k).")
    
    if str(repayment).lower() == 'restart':
        return restart_chat()
    
    if 'k' in repayment:
        repayment = float(repayment.replace('k', '')) * 1000
    else:
        repayment = float(repayment)
    
    lead = Lead.query.filter_by(phone_number=phone_number).first()
    if lead:
        lead.current_repayment = repayment
        db.session.commit()
    
    return send_message(phone_number, "If you know your existing housing loan's interest rate, please enter it. Otherwise, type 'skip'.")
