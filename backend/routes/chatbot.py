import logging
import time
import traceback
import json
import datetime
import os  
from flask import Blueprint, request, jsonify
from backend.utils.calculation import calculate_refinance_savings
from backend.utils.whatsapp import send_whatsapp_message
from backend.models import User, Lead
from backend.extensions import db
from openai import OpenAI
from backend.utils.presets import get_preset_response  

logging.basicConfig(level=logging.DEBUG)

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

chatbot_bp = Blueprint('chatbot', __name__)

# User Data Storage
USER_STATE = {}

# Load language files
# **No Changes Here**

STEP_CONFIG = {
    'choose_language': {
        'message': "choose_language_message",
        'next_step': 'get_name',
        'validator': lambda x, user_data=None: ''.join(filter(str.isdigit, x)) in ['1', '2', '3']
    },
    'get_name': {
        'message': 'name_message',
        'next_step': 'get_age',
        'validator': lambda x, user_data=None: x.replace(' ', '').isalpha()  # Allow spaces in names
    },
    'get_age': {
        'message': 'age_message',
        'next_step': 'get_loan_amount',
        'validator': lambda x, user_data=None: x.isdigit() and 18 <= int(x) <= 70
    },
    'get_loan_amount': {
        'message': 'loan_amount_message',
        'next_step': 'get_loan_tenure',
        'validator': lambda x, user_data=None: x.isdigit()
    },
    'get_loan_tenure': {
        'message': 'loan_tenure_message',
        'next_step': 'get_monthly_repayment',
        'validator': lambda x, user_data=None: x.isdigit() and 1 <= int(x) <= 40
    },
    'get_monthly_repayment': {
        'message': 'repayment_message',
        'next_step': 'get_interest_rate',
        'validator': lambda x, user_data=None: x.isdigit()
    },
    'get_interest_rate': {
        'message': 'interest_rate_message',
        'next_step': 'get_remaining_tenure',
        'validator': lambda x, user_data=None: x.lower() == 'skip' or (x.replace('.', '').isdigit() and 3 <= float(x) <= 10)
    },
    'get_remaining_tenure': {
        'message': 'remaining_tenure_message',
        'next_step': 'process_completion',
        'validator': lambda x, user_data: x.lower() == 'skip' or (x.isdigit() and int(x) < user_data.get('original_loan_tenure', 0))
    },
    'process_completion': {
        'message': 'completion_message',
        'next_step': None,
        'validator': lambda x, user_data=None: True
    }
}

@chatbot_bp.route('/process_message', methods=['POST'])
def process_message():
    try:
        # Parse incoming request
        data = request.get_json()
        phone_number = data['entry'][0]['changes'][0]['value']['contacts'][0]['wa_id']
        message_body = data['entry'][0]['changes'][0]['value']['messages'][0]['text']['body'].strip()
        
        logging.debug(f"🧐 Current message: {message_body} | From: {phone_number}")
        
        if message_body.lower() == 'restart':
            USER_STATE[phone_number] = {'current_step': 'choose_language', 'mode': 'active', 'language_code': None}
            send_whatsapp_message(phone_number, get_message('choose_language', 'en'))
            return jsonify({"status": "success"}), 200

        if phone_number not in USER_STATE:
            USER_STATE[phone_number] = {'current_step': 'choose_language', 'mode': 'active', 'language_code': None}

        user_data = USER_STATE[phone_number]
        current_step = user_data.get('current_step', 'choose_language')
        
        if current_step == 'choose_language':
            message_body = ''.join(filter(str.isdigit, message_body))  # Clean only for choose_language
        
        step_info = STEP_CONFIG.get(current_step)
        if not step_info:
            logging.error(f"Step '{current_step}' not found in STEP_CONFIG.")
            return jsonify({"status": "error"}), 500

        if not step_info['validator'](message_body, user_data):
            logging.warning(f"⚠️ Validation failed for step '{current_step}' | Input: '{message_body}'")
            send_whatsapp_message(phone_number, get_message(current_step, user_data['language_code'] or 'en'))
            return jsonify({"status": "failed"}), 400

        process_user_input(current_step, user_data, message_body, user_data['language_code'] or 'en')
        
        next_step = step_info.get('next_step')
        if next_step:
            user_data['current_step'] = next_step
            logging.info(f"🪄 Step transition: {current_step} ➡️ {next_step}")
            send_whatsapp_message(phone_number, get_message(next_step, user_data['language_code'] or 'en'))
        
        return jsonify({"status": "success"}), 200

    except Exception as e:
        logging.error(f"❌ Unexpected error in process_message: {e}", exc_info=True)
        send_whatsapp_message(phone_number, "An unexpected error occurred. Please try again.")
        return jsonify({"status": "error"}), 500

def process_user_input(current_step, user_data, message_body, language_code):
    if current_step == 'get_name':
        user_data['name'] = message_body.strip().title()
    elif current_step == 'get_age':
        user_data['age'] = int(message_body)
    elif current_step == 'get_loan_amount':
        user_data['original_loan_amount'] = int(message_body)
    elif current_step == 'get_loan_tenure':
        user_data['original_loan_tenure'] = int(message_body)
    elif current_step == 'get_monthly_repayment':
        user_data['current_repayment'] = int(message_body)
    elif current_step == 'get_interest_rate' and message_body.lower() != 'skip':
        user_data['interest_rate'] = float(message_body)
    elif current_step == 'get_remaining_tenure' and message_body.lower() != 'skip':
        user_data['remaining_tenure'] = int(message_body)

    elif current_step == 'process_completion':  
        user_data['mode'] = 'query'  
    # Logic for process completion
        logging.info(f"Processing completion for phone_number: {user_data.get('phone_number')}")
        user_data['mode'] = 'query'
        return jsonify({"status": "success"}), 200

def get_message(key, language_code):
    try:
        # First, check if the key is part of STEP_CONFIG
        if key in STEP_CONFIG:
            step_key = STEP_CONFIG[key]['message']
        else:
            # If the key is not a step, use it as-is
            step_key = key

        logging.debug(f"Trying to get message for key: '{step_key}' in language: '{language_code}'")

        # Get the available keys from the selected language file
        if language_code in LANGUAGE_OPTIONS:
            available_keys = list(LANGUAGE_OPTIONS[language_code].keys())
            logging.debug(f"Available keys in '{language_code}' file: {available_keys}")
        else:
            logging.error(f"Language '{language_code}' is not found in LANGUAGE_OPTIONS.")
            return 'Message not found'

        # Get the message from the language file
        message = LANGUAGE_OPTIONS.get(language_code, {}).get(step_key, 'Message not found')
        if message == 'Message not found':
            logging.error(f"Message key '{step_key}' not found in language file for {language_code}. Available keys: {available_keys if 'available_keys' in locals() else 'No keys loaded'}")
    except Exception as e:
        logging.error(f"Error while getting message key '{key}' for language '{language_code}': {e}")
        message = 'Message not found'
    
    return message


@chatbot_bp.route('/process_message', methods=['POST'])
def process_message():
    try:
        # 📩 Parse incoming request
        data = request.get_json()
        logging.debug(f"📩 Full incoming request: {json.dumps(data, indent=2)}")

        # Extract phone number and message body
        try:
            phone_number = data['entry'][0]['changes'][0]['value']['contacts'][0]['wa_id']
            message_body = data['entry'][0]['changes'][0]['value']['messages'][0]['text']['body'].strip().lower()
            logging.debug(f"☎️ Extracted phone number: {phone_number} | 📨 Message body: '{message_body}'")
        except (KeyError, IndexError, AttributeError) as e:
            logging.error(f"❌ Error extracting phone_number or message_body: {e}", exc_info=True)
            return jsonify({"status": "error", "message": "Invalid request format"}), 400

        # Clean user input (keep only numbers)
        message_body_cleaned = ''.join(filter(str.isdigit, message_body))  
        logging.debug(f"🧐 Cleaned user input for language selection: '{message_body_cleaned}'")

        # Handle 'restart' command to reset the state
        if message_body == 'restart':
            logging.info(f"🔄 User requested a restart. Resetting state for {phone_number}.")
            USER_STATE[phone_number] = {'current_step': 'choose_language', 'mode': 'active', 'language_code': None}
            message = get_message('choose_language', 'en')
            logging.debug(f"🔄 Restart message for {phone_number}: {message}")
            send_whatsapp_message(phone_number, message)
            return jsonify({"status": "success"}), 200

        # Initialize user state if phone number is not in USER_STATE
        if phone_number not in USER_STATE:
            logging.info(f"🆕 New user detected. Initializing USER_STATE for {phone_number}.")
            USER_STATE[phone_number] = {
                'current_step': 'choose_language',
                'mode': 'active',
                'language_code': None,
                'name': None,
                'age': None,
                'original_loan_amount': None,
                'original_loan_tenure': None,
                'current_repayment': None,
                'interest_rate': None,
                'remaining_tenure': None,
            }

        # Get user data and current step
        user_data = USER_STATE[phone_number]
        current_step = user_data.get('current_step', 'choose_language')

        logging.debug(f"📊 Current step for {phone_number}: {current_step}")
        logging.debug(f"📊 Current USER_STATE for {phone_number}: {json.dumps(user_data, indent=2)}")

        # If user is in query mode, handle GPT queries
        if user_data.get('mode') == 'query':
            logging.info(f"🔍 User is in query mode. Handling GPT query for {phone_number}.")
            handle_gpt_query(message_body, user_data, phone_number)
            return jsonify({"status": "success"}), 200

        # Handle language selection step
        if current_step == 'choose_language':
            message_body_cleaned = ''.join(filter(str.isdigit, message_body))  # Clean only during language selection
            if message_body_cleaned in ['1', '2', '3']:
                user_data['language_code'] = ['en', 'ms', 'zh'][int(message_body_cleaned) - 1]
                user_data['current_step'] = STEP_CONFIG['choose_language']['next_step']
                logging.info(f"🌐 Language set to '{user_data['language_code']}' for {phone_number}. Moving to next step: {user_data['current_step']}")
            else:
                message = get_message('choose_language', 'en')
                logging.warning(f"⚠️ Invalid language selection. User input: '{message_body}'. Resending language options to {phone_number}.")
                send_whatsapp_message(phone_number, message)
                return jsonify({"status": "failed"}), 400

        # Get the step configuration for the current step
        step_info = STEP_CONFIG.get(current_step)
        if not step_info:
            logging.error(f"❌ Step '{current_step}' not found in STEP_CONFIG.")
            send_whatsapp_message(phone_number, "An error occurred. Please try again later.")
            return jsonify({"status": "error"}), 500

        # Validate the user's input for the current step
        if not step_info['validator'](message_body, user_data):
            message = get_message(current_step, user_data.get('language_code', 'en'))
            logging.warning(f"⚠️ Validation failed for step '{current_step}'. User input: '{message_body}'. Sending message: {message}")
            send_whatsapp_message(phone_number, message)
            return jsonify({"status": "failed"}), 400

        logging.debug(f"✅ Validation passed for step '{current_step}'. User input: '{message_body}'")
        
        # Process user input and update the state
        process_user_input(current_step, user_data, message_body, user_data.get('language_code', 'en'))
        prev_step = user_data['current_step']
        user_data['current_step'] = step_info.get('next_step')
        logging.info(f"🪄 Step transition: '{prev_step}' ➡️ '{user_data['current_step']}' for {phone_number}")

        if user_data['current_step'] == 'process_completion':
            logging.info(f"📦 Handling process completion for {phone_number}.")
            return handle_process_completion(phone_number, user_data)

        # Get the message for the next step
        message = get_message(user_data['current_step'], user_data.get('language_code', 'en'))
        if not message or message == 'Message not found':
            logging.error(f"❌ Message for step '{user_data['current_step']}' not found in language file.")
            send_whatsapp_message(phone_number, "We encountered an issue processing your request. Please try again later.")
            return jsonify({"status": "error"}), 500

        logging.info(f"📲 Sending message for next step: '{user_data['current_step']}' to {phone_number}")
        send_whatsapp_message(phone_number, message)
        
        return jsonify({"status": "success"}), 200

    except Exception as e:
        logging.error(f"❌ Unexpected error in process_message: {e}", exc_info=True)
        
        user_data = USER_STATE.get(phone_number, {})
        if user_data.get('mode') == 'query':
            logging.info(f"🔁 Switching to query mode for {phone_number}.")
            handle_gpt_query(message_body, user_data, phone_number)
            return jsonify({"status": "success"}), 200
        
        send_whatsapp_message(phone_number, "An unexpected error occurred. Please try again or contact support.")
        return jsonify({"status": "error"}), 500


def handle_process_completion(phone_number, user_data):
    calculation_results = calculate_refinance_savings(user_data['original_loan_amount'], user_data['original_loan_tenure'], user_data['current_repayment'])
    
    if calculation_results.get('monthly_savings', 0) <= 0:
        message = (
            "Thank you for using FinZo AI! Our analysis shows that your current loan rates are already in great shape. "
            "We’ll be in touch if better offers become available.\n\n"
            "📞 Need help or have questions? Contact our admin directly at wa.me/60167177813.\n"
            "💬 Want to explore refinancing options or have questions on home loans? Our FinZo AI support is ready to assist you at any time!"
        )
        send_whatsapp_message(phone_number, message)
        
        # ✅ Switch the user to query mode after sending the message
        user_data['mode'] = 'query'

        return jsonify({"status": "success"}), 200
    
    summary_messages = prepare_summary_messages(user_data, calculation_results, user_data.get('language_code', 'en'))
    for message in summary_messages:
        send_whatsapp_message(phone_number, message)
    
    send_new_lead_to_admin(phone_number, user_data)
    
    # ✅ Switch the user to query mode after sending the summary messages
    user_data['mode'] = 'query'

    return jsonify({"status": "success"}), 200

def prepare_summary_messages(user_data, calculation_results, language_code):
    """Prepare summary messages to be sent as plain text to the user in their preferred language."""
    
    summary_message_1 = f"{get_message('summary_title_1', language_code)}\n\n" + get_message('summary_content_1', language_code).format(
        current_repayment=f"{user_data['current_repayment']:,.2f}",
        new_repayment=f"{calculation_results['new_monthly_repayment']:,.2f}",
        monthly_savings=f"{calculation_results['monthly_savings']:,.2f}",
        yearly_savings=f"{calculation_results['yearly_savings']:,.2f}",
        lifetime_savings=f"{calculation_results['lifetime_savings']:,.2f}"
    )

    summary_message_2 = f"{get_message('summary_title_2', language_code)}\n\n" + get_message('summary_content_2', language_code).format(
        monthly_savings=f"{calculation_results['monthly_savings']:,.2f}",
        yearly_savings=f"{calculation_results['yearly_savings']:,.2f}",
        lifetime_savings=f"{calculation_results['lifetime_savings']:,.2f}",
        years_saved=calculation_results['years_saved'],
        months_saved=calculation_results['months_saved']
    )

    summary_message_3 = f"{get_message('summary_title_3', language_code)}\n\n" + get_message('summary_content_3', language_code).format(
        whatsapp_link="wa.me/60167177813"
    )

    return [summary_message_1, summary_message_2, summary_message_3]

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

      lead = Lead(
    user_id=user.id,
    phone_number=user.phone_number,
    name=user_data.get('name', 'Unnamed Lead'),  # This ensures a name is always provided
    original_loan_amount=user_data.get('original_loan_amount'),
    original_loan_tenure=user_data.get('original_loan_tenure'),
    current_repayment=user_data.get('current_repayment'),
    new_repayment=calculation_results.get('new_monthly_repayment', 0.0),
    monthly_savings=calculation_results.get('monthly_savings', 0.0),
    yearly_savings=calculation_results.get('yearly_savings', 0.0),
    total_savings=calculation_results.get('lifetime_savings', 0.0),
    years_saved=calculation_results.get('years_saved', 0.0)
)

      db.session.add(lead)
      db.session.commit()

      logging.info(f"✅ Database updated successfully for user {phone_number}")

   except Exception as e:
      logging.error(f"❌ Error updating database for {phone_number}: {e}")

def send_new_lead_to_admin(phone_number, user_data):
    admin_number = os.getenv('ADMIN_PHONE_NUMBER')
    if not admin_number:
        logging.error("ADMIN_PHONE_NUMBER not set in environment variables.")
        return
    
    message = (
        f"📢 New Lead Alert! 📢\n\n"
        f"👤 Name: {user_data.get('name', 'Unknown')}\n"
        f"📞 Phone: {phone_number}\n"
        f"💰 Loan Amount: RM {user_data.get('original_loan_amount')}\n"
        f"📅 Tenure: {user_data.get('original_loan_tenure')} years\n"
        f"📉 Monthly Repayment: RM {user_data.get('current_repayment')}\n\n"
        f"👉 Click here to chat directly: https://wa.me/{phone_number}"
    )
    send_whatsapp_message(admin_number, message)

def handle_gpt_query(question, user_data, phone_number):
    """Handles GPT query requests from users with a limit of 15 questions per 24-hour period."""
    
    # Set the daily query limit (15 questions per day)
    GPT_QUERY_LIMIT = 15
    
    # Check if 24 hours have passed since the user's last question
    current_time = datetime.datetime.now()
    last_question_time = user_data.get('last_question_time', None)
    
    if last_question_time:
        # Check if 24 hours have passed
        time_difference = current_time - last_question_time
        if time_difference.total_seconds() > 86400:  # 24 hours = 86400 seconds
            user_data['gpt_query_count'] = 0  # Reset daily limit
            logging.info(f"✅ Reset query count for user {phone_number} after 24 hours.")

    # Update the time of the user's most recent query
    user_data['last_question_time'] = current_time
    
    # Check if the user has reached the daily limit of 15 questions
    if user_data.get('gpt_query_count', 0) >= GPT_QUERY_LIMIT:
        message = (
            "Thank you for using FinZo AI!\n"
            "To ensure fair access to all users, we've implemented a fair usage policy with a daily limit of 15 questions per day.\n\n"
            "You've reached your daily limit, but don't worry! Your limit will reset in 24 hours. \n"
            "If you'd like immediate assistance, feel free to reach out to our admin directly at: wa.me/60167177813\n\n"
            "We appreciate your understanding and look forward to supporting you again tomorrow! 🚀"
        )
        send_whatsapp_message(phone_number, message)
        return

    # Increment the user's GPT query count
    user_data['gpt_query_count'] = user_data.get('gpt_query_count', 0) + 1

    # Notify the user when they have 10 or 5 questions remaining
    questions_left = GPT_QUERY_LIMIT - user_data['gpt_query_count']
    if questions_left == 10:
        send_whatsapp_message(phone_number, "🤖 You have 10 questions remaining today.")
    elif questions_left == 5:
        send_whatsapp_message(phone_number, "🤖 You have 5 questions remaining today.")

    try:
        # Step 1: Check if a preset response exists for the question
        response = get_preset_response(question, user_data.get('language_code', 'en'))
        
        if response:
            logging.info(f"✅ Preset response found for query: {question}")
            message = response
        else:
            # Step 2: Call OpenAI GPT-3.5-turbo if no preset response is found
            logging.info(f"❌ No preset found. Falling back to GPT-3.5-turbo for query: {question}")
            
            try:
                response = client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[{"role": "user", "content": question}]
            )
                logging.info(f"Response type: {type(response)}")
                logging.info(f"Response structure: {dir(response)}")
                logging.info(f"First choice type: {type(response.choices[0])}")
                logging.info(f"Message type: {type(response.choices[0].message)}")
    
                message = response.choices[0].message.content
            except Exception as e:
                logging.error(f"❌ Error while calling GPT for {phone_number}: {str(e)}")
                logging.error(f"Error type: {type(e)}")
                message = (
                    "We're currently experiencing issues processing your request. "
                    "Please try again later or contact our admin for assistance: wa.me/60167177813"
                )
        
    except Exception as e:
        logging.error(f"❌ Unexpected error while handling query for {phone_number}: {str(e)}")
        message = (
            "We're currently experiencing issues processing your request. "
            "Please try again later or contact our admin for assistance: wa.me/60167177813"
        )

    # Send the GPT response to the user
    send_whatsapp_message(phone_number, message)