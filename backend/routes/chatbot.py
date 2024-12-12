from flask import Blueprint, request, jsonify
from datetime import datetime, timedelta
from ..extensions import db
from ..models import User, Lead, ChatLog, BankRate

chatbot_bp = Blueprint('chatbot', __name__)

@chatbot_bp.route('/start', methods=['POST'])
def start_chat():
    """Welcome message for the user."""
    return jsonify({
        "message": "Welcome to FinZo Advisory, your personal refinancing assistant! What's your name?"
    })

@chatbot_bp.route('/get_name', methods=['POST'])
def get_name():
    data = request.get_json()
    phone_number = data.get('phone_number')
    name = data.get('name')
    if not name:
        return jsonify({"message": "Please provide your name to continue."})

    user = User.query.filter_by(wa_id=phone_number).first()
    if not user:
        user = User(wa_id=phone_number, name=name)
        db.session.add(user)
        db.session.commit()

    return jsonify({"message": f"Thanks, {name}! How old are you? (18-70)"})

@chatbot_bp.route('/calculate_savings', methods=['POST'])
def calculate_savings():
    """Calculate the savings for a user based on bank rates."""
    data = request.get_json()
    phone_number = data.get('phone_number')
    lead = Lead.query.filter_by(phone_number=phone_number).first()

    if not lead:
        return jsonify({"message": "We could not find your lead information. Please restart the process."})

    # Sample logic for calculation (replace with real logic)
    current_installment = lead.current_repayment
    rate = BankRate.query.filter_by(bank_name='Bank A').first()
    new_interest_rate = rate.interest_rate / 100

    estimated_new_installment = (current_installment * new_interest_rate) / 12
    monthly_saved = current_installment - estimated_new_installment
    yearly_saved = monthly_saved * 12
    total_saved = yearly_saved * lead.original_loan_tenure
    years_saved = total_saved // current_installment
    months_saved = (total_saved % current_installment) // (current_installment / 12)
    
    lead.new_repayment = estimated_new_installment
    lead.monthly_savings = monthly_saved
    lead.yearly_savings = yearly_saved
    lead.total_savings = total_saved
    lead.years_saved = float(years_saved) + float(months_saved / 12)
    db.session.commit()

    return jsonify({
        "message": "Calculation complete! Here is your savings summary.",
        "summary": {
            "current_installment": current_installment,
            "new_installment": estimated_new_installment,
            "monthly_saved": monthly_saved,
            "yearly_saved": yearly_saved,
            "total_saved": total_saved,
            "years_saved": f"{int(years_saved)} year(s) {int(months_saved)} month(s)"
        }
    })
