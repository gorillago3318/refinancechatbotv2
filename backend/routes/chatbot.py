import os
from flask import Blueprint, request, jsonify
from backend.helpers import get_lead, update_lead_state, reset_lead_state
from backend.utils.whatsapp import send_whatsapp_message, send_message_to_admin
from backend.extensions import db
import json
import logging
import re
from backend.utils.calculation import calculate_savings, format_years_saved, find_best_bank_rate
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
        text = message.get('text', {}).get('body', '').strip()
    except (KeyError, IndexError) as e:
        return jsonify({"error": "Invalid payload"}), 400

    lead = get_lead(from_number)
    if not lead:
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

    elif state == 'get_repayment':
        amount = extract_number(text)
        if amount:
            lead.current_repayment = amount
            update_lead_state(lead, 'get_optional_tenure')
            send_whatsapp_message(from_number, "If you'd like, provide the remaining tenure of your loan.\nType 'skip' to skip this step.")
        else:
            send_whatsapp_message(from_number, "Invalid amount. Please provide your monthly repayment.")
        return jsonify({"status": "repayment captured"}), 200
    
    elif state == 'get_optional_tenure':
        if text.lower() == 'skip':
            update_lead_state(lead, 'get_optional_interest')
            send_whatsapp_message(from_number, "If you'd like, provide the current interest rate of your loan (e.g., 4.5%).\nType 'skip' to skip this step.")
        elif text.isdigit():
            lead.remaining_tenure = int(text)
            update_lead_state(lead, 'get_optional_interest')
            send_whatsapp_message(from_number, "If you'd like, provide the current interest rate of your loan (e.g., 4.5%).\nType 'skip' to skip this step.")
        else:
            send_whatsapp_message(from_number, "Invalid tenure. Please provide the remaining tenure as a whole number (e.g., 20) or type 'skip'.")
        return jsonify({"status": "optional tenure captured"}), 200
    
    elif state == 'get_optional_interest':
        if text.lower() == 'skip':
            update_lead_state(lead, 'calculate')
            # Call function to calculate and display summary
        else:
            try:
                interest = float(text)
                if 3 <= interest <= 10:
                    lead.interest_rate = interest
                    update_lead_state(lead, 'calculate')
                    # Call function to calculate and display summary
                else:
                    send_whatsapp_message(from_number, "Invalid rate. Provide a rate between 3% and 10%.")
            except ValueError:
                send_whatsapp_message(from_number, "Invalid rate. Please provide a percentage (e.g., 4.5%).")

def calculate_and_display_summary(lead, from_number):
    """ Calculate the refinance savings and send the summary to the user and admin. """
    best_rate = find_best_bank_rate(lead.original_loan_amount)
    estimated_new_repayment, monthly_savings, yearly_savings, total_savings = calculate_savings(
        original_loan_amount=lead.original_loan_amount,
        original_tenure=lead.original_loan_tenure,
        current_repayment=lead.current_repayment,
        interest_rate=best_rate
    )
    years_saved = format_years_saved(total_savings / lead.current_repayment)
    
    lead.new_repayment = estimated_new_repayment
    lead.monthly_savings = monthly_savings
    lead.yearly_savings = yearly_savings
    lead.total_savings = total_savings
    lead.years_saved = years_saved
    db.session.commit()
    
    if total_savings > 0:
        summary_message = (
            f"💰 Congratulations! You can save RM {total_savings:,.2f} if you refinance.\n\n"
            "Our specialist will assist you with a detailed report and refinancing guidance.\n"
            "This service is 100% free of charge!\n\n"
            "📞 Need help? Contact our admin directly: wa.me/60167177813."
        )
    else:
        summary_message = (
            "🎉 Great news! Your current loan is one of the best rates available.\n\n"
            "Our specialist will continue to monitor rates for better deals. Stay tuned!"
        )
    send_whatsapp_message(from_number, summary_message)
    
    admin_message = (
        f"New Lead Alert!\n\n"
        f"📱 Phone: wa.me/{lead.phone_number}\n"
        f"👤 Name: {lead.name}\n"
        f"🕒 Age: {lead.age}\n"
        f"💰 Loan Amount: RM {lead.original_loan_amount:,.2f}\n"
        f"📆 Tenure: {lead.original_loan_tenure} years\n"
        f"💸 Current Repayment: RM {lead.current_repayment:,.2f}\n"
        f"⏳ Remaining Tenure: {lead.remaining_tenure or 'Not provided'}\n"
        f"📈 Interest Rate: {lead.interest_rate or 'Not provided'}%\n"
    )
    send_message_to_admin(admin_message)


def process_calculate_state(lead, from_number):
    """ Process the 'calculate' state. """
    calculate_and_display_summary(lead, from_number)
    update_lead_state(lead, 'end')
    send_whatsapp_message(from_number, "If you have any questions about housing loans or refinancing, I'm here to help!")
    return jsonify({"status": "summary displayed"}), 200
