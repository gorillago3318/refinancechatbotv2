import logging
import time
import traceback
from flask import Blueprint, request, jsonify
from backend.utils.calculation import calculate_refinance_savings
from backend.utils.whatsapp import send_whatsapp_message
from backend.models import User, Lead
from backend.extensions import db

chatbot_bp = Blueprint('chatbot', __name__)

# User Data Storage
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
        'message': "📝 *To kick things off, we'll need your NAME* — so we know who to address when sharing your savings story!",
        'next_step': 'get_age',
        'validator': lambda x: len(x.strip()) > 0
    },
    'get_age': {
        'message': "🎉 *Next up, we'll need your AGE* \n\n(between **18 and 70**). This helps us tailor the best refinancing options for you!\n\n",
        'next_step': 'get_loan_amount',
        'validator': lambda x: x.isdigit() and 18 <= int(x) <= 70
    },
    'get_loan_amount': {
        'message': "💰 *We need to know your ORIGINAL LOAN AMOUNT* — this is the total amount you borrowed when you first took out your home loan.\n\n"
                   "Here's how you can enter it:\n"
                   " * *100k* = RM100,000\n"
                   " * *1.2m* = RM1,200,000\n\n"
                   "This amount helps us calculate your savings potential, so make sure it matches the original amount you borrowed for the property.",
        'next_step': 'get_loan_tenure',
        'validator': lambda x: x.replace('k', '').replace('m', '').replace('.', '').isdigit()
    },
    'get_loan_tenure': {
        'message': "📅 *Next, we will need to know your ORIGINAL LOAN TENURE* — this is the total number of years you agreed to repay your home loan when you first signed up.\n\n"
                   "💡 **Example:**\n"
                   " * If your loan was for 30 years, type *30*.\n"
                   " * If it was for 25 years, type *25*.",
        'next_step': 'get_monthly_repayment',
        'validator': lambda x: x.isdigit() and 1 <= int(x) <= 40
    },
    'get_monthly_repayment': {
        'message': "💸 *Most Importantly, we need to know your CURRENT MONTHLY INSTALLMENT* — this is the amount you're currently paying to the bank every month for your home loan.\n\n"
                   "💡 **How to enter it:**\n"
                   " * Type *1.5k* for RM1,500\n"
                   " * Or just type *1500*\n\n"
                   "This info helps us compare your current deal with potential refinancing options — and spot the savings! 💥",
        'next_step': 'get_interest_rate',
        'validator': lambda x: x.replace('k', '').replace('.', '').isdigit()
    },
    'get_interest_rate': {
        'message': "📈 Do you remember your current loan's *INTEREST RATE*? If you're not sure, just type **SKIP** \n\n— No worries, we can still calculate your potential savings! This is the percentage rate your bank charges you on your loan.\n\n"
                   "💡 **How to enter it:**\n"
                   " * If your rate is 3.85%, type *3.85*\n",
        'next_step': 'get_remaining_tenure',
        'validator': lambda x: x.lower() == 'skip' or x.replace('.', '').isdigit()
    },
    'get_remaining_tenure': {
        'message': "⏳ *Almost there — How many years are LEFT ON YOUR LOAN*? This is the number of years you still have to pay before your loan is fully paid off.\n\n"
                   "💡 **How to enter it:**\n"
                   " * If you have *10 years* left, type *10*.\n"
                   " * Not sure? No problem — just type *SKIP* and we'll still give you an estimate.\n\n"
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
    """ Processes the user input for the current step and updates the user data accordingly. """
    try:
        logging.info(f"Processing input for step: {current_step} with message: {message_body}")
        
        if current_step == 'get_name':
            user_data['name'] = message_body.strip().title()
        
        elif current_step == 'get_age' and message_body.isdigit():
            user_data['age'] = int(message_body)
        
        elif current_step == 'get_loan_amount':
            try:
                if 'k' in message_body:
                    user_data['original_loan_amount'] = float(message_body.replace('k', '').replace(',', '').strip()) * 1000
                elif 'm' in message_body:
                    user_data['original_loan_amount'] = float(message_body.replace('m', '').replace(',', '').strip()) * 1000000
                else:
                    user_data['original_loan_amount'] = float(message_body.replace(',', '').strip())
            except ValueError:
                logging.error(f"Invalid loan amount input: {message_body}")
                raise
        
        elif current_step == 'get_loan_tenure' and message_body.isdigit():
            user_data['original_loan_tenure'] = int(message_body)
        
        elif current_step == 'get_monthly_repayment':
            try:
                if 'k' in message_body:
                    user_data['current_repayment'] = float(message_body.replace('k', '').replace(',', '').strip()) * 1000
                else:
                    user_data['current_repayment'] = float(message_body.replace(',', '').strip())
            except ValueError:
                logging.error(f"Invalid monthly repayment input: {message_body}")
                raise
        
        elif current_step == 'get_interest_rate':
            if message_body.lower() != 'skip' and message_body.replace('.', '').isdigit():
                user_data['interest_rate'] = float(message_body)
        
        elif current_step == 'get_remaining_tenure':
            if message_body.lower() != 'skip' and message_body.isdigit():
                user_data['remaining_tenure'] = int(message_body)

        logging.info(f"Updated user data for step '{current_step}': {user_data}")
    
    except ValueError as ve:
        logging.error(f"ValueError while processing step '{current_step}' with input '{message_body}': {ve}")
        raise
    
    except Exception as e:
        logging.error(f"Unexpected error while processing step '{current_step}' with input '{message_body}': {e}")
        raise

@chatbot_bp.route('/process_message', methods=['POST'])
def process_message():
    try:
        data = request.get_json()
        
        phone_number = data['entry'][0]['changes'][0]['value']['contacts'][0]['wa_id']
        message_body = data['entry'][0]['changes'][0]['value']['messages'][0]['text']['body'].strip().lower()

        # Handle restart command
        if message_body == 'restart':
            USER_STATE[phone_number] = {'current_step': 'welcome_message'}
            welcome_msg = STEP_CONFIG['welcome_message']['message']
            send_whatsapp_message(phone_number, welcome_msg)
            USER_STATE[phone_number]['current_step'] = 'get_name'
            get_name_msg = STEP_CONFIG['get_name']['message']
            send_whatsapp_message(phone_number, get_name_msg)
            logging.info(f"User {phone_number} restarted. Current step is now 'get_name'.")
            return jsonify({"status": "success", "message": "Restarted and moved directly to get_name"}), 200

        # Initialize user state if not exists
        if phone_number not in USER_STATE:
            USER_STATE[phone_number] = {'current_step': 'get_name'}

        user_data = USER_STATE[phone_number]
        current_step = user_data.get('current_step', 'get_name')
        
        logging.info(f"Current step for {phone_number}: {current_step}")

        # Validate input based on current step
        step_info = STEP_CONFIG.get(current_step)
        
        if not step_info or not step_info['validator'](message_body):
            # If invalid input, resend the current step's message
            send_whatsapp_message(phone_number, step_info['message'])
            return jsonify({"status": "failed", "message": "Invalid input"}), 400

        # Process user input
        process_user_input(current_step, user_data, message_body)
        
        # Update next step
        user_data['current_step'] = step_info['next_step']
        
        logging.info(f"Updated user data for {phone_number}: {user_data}")
        
        # Handle process completion
        if user_data['current_step'] == 'process_completion':
            return handle_process_completion(phone_number, user_data)

        # Send next message
        next_message = STEP_CONFIG[user_data['current_step']]['message']
        send_whatsapp_message(phone_number, next_message)
        
        return jsonify({"status": "success", "message": next_message}), 200
    
    except Exception as e:
        logging.error(f"Unexpected error in process_message: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500   
                
def handle_process_completion(phone_number, user_data):
    """ Handles completion of process by calculating refinance savings and sending results. """
    try:
       # Extract relevant user data for calculation
       original_loan_amount = user_data.get('original_loan_amount')
       original_loan_tenure = user_data.get('original_loan_tenure')
       current_repayment = user_data.get('current_repayment')

       calculation_results = calculate_refinance_savings(
           original_loan_amount=original_loan_amount,
           original_loan_tenure=original_loan_tenure,
           current_monthly_repayment=current_repayment
       )

       if calculation_results.get('error'):
           logging.error(f"❌ Error in calculation: {calculation_results['error']}")
           send_whatsapp_message(phone_number, "An error occurred while calculating your refinance savings.")
           return jsonify({"status": "failed", "message": calculation_results['error']}), 500

       # Prepare summary messages based on calculations...
       summary_messages = prepare_summary_messages(user_data, calculation_results)

       # Send summary messages...
       for msg in summary_messages:
           send_whatsapp_message(phone_number, msg)

       # Update database with results...
       update_database(phone_number, user_data, calculation_results)

       USER_STATE.pop(phone_number, None)
       
       return jsonify({"status": "success", "message": "Process complete"}), 200

    except Exception as e:
       logging.error(f"Error during process_completion: {e}")

def prepare_summary_messages(user_data, calculation_results):
   """ Prepares summary messages based on calculated results. """
   monthly_savings = calculation_results.get('monthly_savings', 0)
   yearly_savings = calculation_results.get('yearly_savings', 0)
   lifetime_savings = calculation_results.get('lifetime_savings', 0)
   years_saved = calculation_results.get('years_saved', 0)
   months_saved = calculation_results.get('months_saved', 0)

   summary_messages = [
       f"🏦 **Refinance Savings Summary** 🏦\n\n"
       f"📅 *Current Monthly Repayment: RM {user_data.get('current_repayment', 0):,.2f}* \n"
       f"📉 *Estimated New Repayment: RM {calculation_results.get('new_monthly_repayment', 0):,.2f}* \n"
       f"💸 *Monthly Savings: RM {monthly_savings:,.2f}* \n"
       f"💥 *Yearly Savings: RM {yearly_savings:,.2f}* \n"
       f"💰 *Total Savings Over the Loan Term: RM {lifetime_savings:,.2f}*\n",

       f"🎉 **GOOD NEWS!** 🎉\n\n"
       f"By refinancing, you could save up to *RM {monthly_savings:,.2f} every month*, "
       f"which adds up to *RM {yearly_savings:,.2f} every year* and a total of "
       f"*RM {lifetime_savings:,.2f} over the entire loan term*! \n"
       f"This is like saving *{years_saved} year(s) and {months_saved} month(s) worth of your current repayments*! 🚀",

       f"🔍 *What's next?* A specialist will be assigned to generate a *FULL DETAILED REPORT* for you — "
       f"*free of charge and with no obligations!* "
       f"They can also assist you if you decide to refinance.\n\n"
       f"📞 *Need help or have questions?* Contact our admin directly at **wa.me/60167177813**.\n\n"
       f"💬 *Got more questions about refinancing or home loans?* Ask away! FinZo AI is here to provide the best possible answers for you! 🚀"
   ]

   return summary_messages

def update_database(phone_number, user_data, calculation_results):
   """ Updates the database with the user's input data and calculation results. """
   try:
      user = User.query.filter_by(wa_id=phone_number).first()
      if not user:
          user = User(wa_id=phone_number,
                      phone_number=phone_number,
                      name=user_data.get('name'),
                      age=user_data.get('age'))
          db.session.add(user)
          db.session.flush()

      lead = Lead(user_id=user.id,
                  phone_number=phone_number,
                  original_loan_amount=user_data.get('original_loan_amount'),
                  original_loan_tenure=user_data.get('original_loan_tenure'),
                  current_repayment=user_data.get('current_repayment'),
                  new_repayment=calculation_results.get('new_monthly_repayment', 0.0),
                  monthly_savings=calculation_results.get('monthly_savings', 0.0),
                  yearly_savings=calculation_results.get('yearly_savings', 0.0),
                  total_savings=calculation_results.get('lifetime_savings', 0.0),
                  years_saved=calculation_results.get('years_saved', 0.0))

      db.session.add(lead)
      db.session.commit()

      logging.info(f"✅ Database updated successfully for user {phone_number}")

   except Exception as e:
      logging.error(f"❌ Error updating database for {phone_number}: {e}")