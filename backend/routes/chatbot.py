"""
TODO (Next Enhancements):

1. Make chatbot responses more human and friendly.
2. Shorten and simplify the questions/prompts.
3. Ensure proper line breaks in the summary message.
4. Split the summary into multiple WhatsApp messages with a 2-second gap between sends.
5. Reintroduce the "Great job, you're all set!" message before the summary, then wait 5 seconds before sending the summary.
6. Integrate ChatGPT 3.5 Turbo:
   - Allow up to 5 user questions before prompting the user to contact an admin.
7. Organize and utilize a preset JSON file to guide GPT 3.5 Turbo responses.
8. Check and implement PostgreSQL database linkage to store leads and states.
9. Add language selection and support for multiple languages.
10. Send a WhatsApp notification to the admin number whenever a new lead completes their initial data collection.
"""

import logging
from flask import Blueprint, request, jsonify, current_app
from backend.utils.calculation import calculate_refinance_savings  
from backend.utils.whatsapp import send_whatsapp_message  

chatbot_bp = Blueprint('chatbot', __name__)

# User Data Storage (This is a simulated memory-based store; in production, you might want Redis)
USER_STATE = {}

STEP_CONFIG = {
    'welcome_message': {
        'message': "🎉 *Welcome to FinZo AI – Your Personal Savings Hero!* 🎉\n\n"
                   "Looking to save money on your home loan? You're in the right place! Our smart bot makes refinancing simple, clear, and stress-free. We'll show you how much you could save with a better deal. 💸\n\n"
                   "*Stuck at any point?* No worries! Just type **\"restart\"** and we'll start fresh.\n\n"
                   "Ready to see how much you can save? 🚀",
        'next_step': 'get_name',
        'validator': lambda x: True
    },
    'get_name': {
        'message': "📝 *First things first!*\n\n"
                   "To kick things off, we'll need your *full name* — so we know who to address when sharing your savings story!",
        'next_step': 'get_age',
        'validator': lambda x: len(x.strip()) > 0
    },
    'get_age': {
        'message': "🎉 *Awesome! You're doing great!*\n\n"
                   "Next up, we'll need your *age* (between **18 and 70**). This helps us tailor the best refinancing options for you!\n\n"
                   "Go ahead, type it in — we're one step closer to unlocking your savings! 🚀",
        'next_step': 'get_loan_amount',
        'validator': lambda x: x.isdigit() and 18 <= int(x) <= 70
    },
    'get_loan_amount': {
        'message': "💰 *Let's talk numbers!*\n\n"
                   "We need to know your *original loan amount* — this is the total amount you borrowed when you first took out your home loan.\n\n"
                   "Here's how you can enter it:\n"
                   "   * **100k** = RM100,000\n"
                   "   * **1.2m** = RM1,200,000\n\n"
                   "This amount helps us calculate your savings potential, so make sure it matches the original amount you borrowed for the property.",
        'next_step': 'get_loan_tenure',
        'validator': lambda x: x.replace('k', '').replace('m', '').replace('.', '').isdigit()
    },
    'get_loan_tenure': {
        'message': "📅 *Time to set the timeline!*\n\n"
                   "We need to know your *original loan tenure* — this is the total number of years you agreed to repay your home loan when you first signed up.\n\n"
                   "💡 **Example:**\n"
                   "   * If your loan was for 30 years, type **30**.\n"
                   "   * If it was for 25 years, type **25**.",
        'next_step': 'get_monthly_repayment',
        'validator': lambda x: x.isdigit() and 1 <= int(x) <= 40
    },
    'get_monthly_repayment': {
        'message': "💸 *Let's talk about your monthly payments!*\n\n"
                   "We need to know your *current monthly repayment* — this is the amount you're currently paying to the bank every month for your home loan.\n\n"
                   "💡 **How to enter it:**\n"
                   "   * Type **1.5k** for RM1,500\n"
                   "   * Or just type **1500**\n\n"
                   "This info helps us compare your current deal with potential refinancing options — and spot the savings! 💥",
        'next_step': 'get_interest_rate',
        'validator': lambda x: x.replace('k', '').replace('.', '').isdigit()
    },
    'get_interest_rate': {
        'message': "📈 *Let's talk interest — but no pressure!*\n\n"
                   "Do you know your current loan's *interest rate*? This is the percentage rate your bank charges you on your loan.\n\n"
                   "💡 **How to enter it:**\n"
                   "   * If your rate is 3.85%, type **3.85**\n"
                   "   * If you're not sure, just type **skip** — no worries, we can still calculate your potential savings!",
        'next_step': 'get_remaining_tenure',
        'validator': lambda x: x.lower() == 'skip' or x.replace('.', '').isdigit()
    },
    'get_remaining_tenure': {
        'message': "⏳ *Almost there — let's check the clock on your loan!*\n\n"
                   "How many years are *left on your loan*? This is the number of years you still have to pay before your loan is fully paid off.\n\n"
                   "💡 **How to enter it:**\n"
                   "   * If you have **10 years** left, type **10**.\n"
                   "   * Not sure? No problem — just type **skip** and we'll still give you an estimate.\n\n"
                   "This helps us fine-tune your savings potential, but it's totally optional. Let's keep it moving! 🚀",
        'next_step': 'process_completion',
        'validator': lambda x: x.lower() == 'skip' or x.isdigit()
    },
    'process_completion': {
        'message': "🎉 *Great job — you're all set!*\n\n"
                   "We're crunching the numbers to create your personalized *Refinance Savings Summary* 🧮💸.\n\n"
                   "Sit tight for a moment — your potential savings are on the way! 🚀",
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
        message_body = data['entry'][0]['changes'][0]['value']['messages'][0]['text']['body'].strip().lower()
        
        # Handle restart command
        if message_body == 'restart':
            USER_STATE[phone_number] = {'current_step': 'welcome_message'}
            # Send welcome message
            welcome_msg = STEP_CONFIG['welcome_message']['message']
            send_whatsapp_message(phone_number, welcome_msg)
            # Immediately advance to get_name step
            USER_STATE[phone_number]['current_step'] = 'get_name'
            get_name_msg = STEP_CONFIG['get_name']['message']
            send_whatsapp_message(phone_number, get_name_msg)
            return jsonify({"status": "success", "message": "Restarted and moved directly to get_name"}), 200
        
        user_data = USER_STATE.get(phone_number, {'current_step': 'welcome_message'})
        current_step = user_data.get('current_step', 'welcome_message')

        # If user has never interacted before, simulate initial welcome and immediate next step
        if current_step == 'welcome_message' and 'name' not in user_data and message_body != 'restart':
            # Send welcome message
            welcome_msg = STEP_CONFIG['welcome_message']['message']
            send_whatsapp_message(phone_number, welcome_msg)
            # Move directly to get_name step
            USER_STATE[phone_number]['current_step'] = 'get_name'
            get_name_msg = STEP_CONFIG['get_name']['message']
            send_whatsapp_message(phone_number, get_name_msg)
            return jsonify({"status": "success", "message": "Initial welcome and moved directly to get_name"}), 200

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
            # Simulated calculation logic
            monthly_savings = 500
            yearly_savings = monthly_savings * 12
            loan_term_savings = monthly_savings * (30 * 12)
            years_saved = loan_term_savings // user_data.get('current_repayment', monthly_savings)
            months_saved = (loan_term_savings % user_data.get('current_repayment', monthly_savings)) // monthly_savings

            summary_message = f"🏦 **Refinance Savings Summary** 🏦\n\n"
            summary_message += f"📅 **Current Monthly Repayment:** RM {user_data.get('current_repayment', 'N/A')} "
            summary_message += f"📉 **Estimated New Repayment:** RM {user_data.get('current_repayment', 'N/A') - monthly_savings} "
            summary_message += f"💸 **Monthly Savings:** RM {monthly_savings} "
            summary_message += f"💥 **Yearly Savings:** RM {yearly_savings} "
            summary_message += f"💰 **Total Savings Over the Loan Term:** RM {loan_term_savings}\n\n"

            summary_message += f"🎉 **GOOD NEWS!** 🎉\n\n"
            summary_message += f"By refinancing, you could save up to **RM {monthly_savings} every month**, "
            summary_message += f"which adds up to **RM {yearly_savings} every year** and a total of "
            summary_message += f"**RM {loan_term_savings} over the entire loan term**! "
            summary_message += f"To put it into perspective, this is like saving **{years_saved} year(s) "
            summary_message += f"and {months_saved} month(s) worth of your current repayments** "
            summary_message += "— a significant step toward financial freedom!\n\n"

            summary_message += f"🔍 **What's next?** A specialist will be assigned to generate a **full detailed report** for you — *free of charge and with no obligations!* "
            summary_message += "They can also assist you if you decide to refinance.\n\n"
            summary_message += f"📞 **Need help or have questions?** Contact our admin directly at **wa.me/60167177813**.\n\n"
            summary_message += f"💬 **Got more questions about refinancing or home loans?** Ask away! FinZo AI is here to provide the best possible answers for you! 🚀"

            send_whatsapp_message(phone_number, summary_message)
            USER_STATE.pop(phone_number, None)
            return jsonify({"status": "success", "message": "Process complete"}), 200

        next_message = STEP_CONFIG[user_data['current_step']]['message']
        send_whatsapp_message(phone_number, next_message)
        
        return jsonify({"status": "success", "message": next_message}), 200
    except Exception as e:
        logging.error(f"Unexpected error in process_message: {e}")
        # Note: phone_number might not be defined if error happens very early
        if 'phone_number' in locals():
            send_whatsapp_message(phone_number, "An unexpected error occurred.")
        return jsonify({"status": "failed"}), 500
