import logging
from flask import Blueprint, request, jsonify, current_app
from backend.utils.calculation import calculate_refinance_savings  
from backend.utils.whatsapp import send_whatsapp_message  

chatbot_bp = Blueprint('chatbot', __name__)

# User Data Storage (This is a simulated memory-based store; in production, you might want Redis)
USER_STATE = {}

STEP_CONFIG = {
    'welcome_message': {
        'message': "*Welcome to FinZo AI – Refinancing Bot!*\n\n"
                   "We're here to help you estimate your potential savings if you refinance your existing home loan. "
                   "You'll receive a clear comparison of your current loan vs. a potential refinance.\n\n"
                   "*Let's get started!*",
        'next_step': 'get_name',
        'validator': lambda x: True
    },
    'get_name': {
        'message': "To begin, please share your *full name*.",
        'next_step': 'get_age',
        'validator': lambda x: len(x.strip()) > 0
    },
    'get_age': {
        'message': "Please provide your *age* (Must be between *18 and 70* years old).",
        'next_step': 'get_loan_amount',
        'validator': lambda x: x.isdigit() and 18 <= int(x) <= 70
    },
    'get_loan_amount': {
        'message': "What is your *original loan amount*?\n\n"
                   "_Example formats:_\n"
                   "- *100k* (for 100,000)\n"
                   "- *1.2m* (for 1,200,000)",
        'next_step': 'get_loan_tenure',
        'validator': lambda x: x.replace('k', '').replace('m', '').replace('.', '').isdigit()
    },
    'get_loan_tenure': {
        'message': "What was your *original loan tenure* in years? (Choose from *1 to 40* years).",
        'next_step': 'get_monthly_repayment',
        'validator': lambda x: x.isdigit() and 1 <= int(x) <= 40
    },
    'get_monthly_repayment': {
        'message': "What is your *current monthly repayment*?\n\n"
                   "_Example formats:_\n"
                   "- *1.5k* (for 1,500)\n"
                   "- *1500*",
        'next_step': 'get_interest_rate',
        'validator': lambda x: x.replace('k', '').replace('.', '').isdigit()
    },
    'get_interest_rate': {
        'message': "Do you know your current loan's *interest rate*? (e.g., *3.85*%).\n\n"
                   "If you don't know, type *skip*.",
        'next_step': 'get_remaining_tenure',
        'validator': lambda x: x.lower() == 'skip' or x.replace('.', '').isdigit()
    },
    'get_remaining_tenure': {
        'message': "How many years are *left on your loan*?\n\n"
                   "_Example formats:_\n"
                   "- *10* (for 10 years left)\n"
                   "If you're not sure, type *skip*.",
        'next_step': 'process_completion',
        'validator': lambda x: x.lower() == 'skip' or x.isdigit()
    },
    'process_completion': {
        'message': "*Thank you for providing the details!*\n\n"
                   "We are now generating your *refinance savings summary*...",
        'next_step': None,
        'validator': lambda x: True
    }
}

def process_user_input(current_step, user_data, message_body):
    if current_step == 'get_name':
        user_data['name'] = message_body
    elif current_step == 'get_age':
        user_data['age'] = int(message_body)
    elif current_step == 'get_loan_amount':
        if 'k' in message_body:
            user_data['original_loan_amount'] = float(message_body.replace('k', '')) * 1000
        elif 'm' in message_body:
            user_data['original_loan_amount'] = float(message_body.replace('m', '')) * 1000000
        else:
            user_data['original_loan_amount'] = float(message_body)
    elif current_step == 'get_loan_tenure':
        user_data['original_loan_tenure'] = int(message_body)
    elif current_step == 'get_monthly_repayment':
        if 'k' in message_body:
            user_data['current_repayment'] = float(message_body.replace('k', '')) * 1000
        else:
            user_data['current_repayment'] = float(message_body)
    elif current_step == 'get_interest_rate':
        if message_body.lower() != 'skip' and message_body.replace('.', '').isdigit():
            user_data['interest_rate'] = float(message_body)
    elif current_step == 'get_remaining_tenure':
        if message_body.lower() != 'skip' and message_body.isdigit(): 
            user_data['remaining_tenure'] = int(message_body) 

@chatbot_bp.route('/process_message', methods=['POST'])
def process_message():
    try:
        data = request.get_json()
        phone_number = data['entry'][0]['changes'][0]['value']['contacts'][0]['wa_id']
        message_body = data['entry'][0]['changes'][0]['value']['messages'][0]['text']['body'].strip()
        
        user_data = USER_STATE.get(phone_number, {'current_step': 'welcome_message'})
        current_step = user_data.get('current_step', 'welcome_message')
        
        if current_step not in STEP_CONFIG:
            logging.error(f"⚠️ No step info for current step: {current_step} for phone: {phone_number}")
            send_whatsapp_message(phone_number, "An unexpected error occurred.")
            return jsonify({"status": "failed"}), 500
        
        step_info = STEP_CONFIG.get(current_step)
        
        if not step_info['validator'](message_body):
            send_whatsapp_message(phone_number, f"Invalid input. {step_info['message']}")
            return jsonify({"status": "failed"}), 400
        
        process_user_input(current_step, user_data, message_body)
        user_data['current_step'] = step_info['next_step']
        USER_STATE[phone_number] = user_data

        if user_data['current_step'] == 'process_completion':
            summary_message = "*Your refinance savings summary is ready!*\n"
            summary_message += f"*Monthly Savings:* RM 500\n"
            summary_message += f"*Total Savings Over Loan Term:* RM 60,000\n"
            summary_message += f"*Potential New Interest Rate:* 3.85%\n"
            summary_message += f"*Updated Loan Tenure:* 15 years"

            send_whatsapp_message(phone_number, summary_message)
            USER_STATE.pop(phone_number, None)
            return jsonify({"status": "success", "message": "Process complete"}), 200

        next_message = STEP_CONFIG[user_data['current_step']]['message']
        send_whatsapp_message(phone_number, next_message)
        
        return jsonify({"status": "success", "message": next_message}), 200
    except Exception as e:
        logging.error(f"Unexpected error in process_message: {e}")
        send_whatsapp_message(phone_number, "An unexpected error occurred.")
        return jsonify({"status": "failed"}), 500
