import logging
import time
import traceback
import json
from flask import Blueprint, request, jsonify
from backend.utils.calculation import calculate_refinance_savings
from backend.utils.whatsapp import send_whatsapp_message
from backend.models import User, Lead
from backend.extensions import db

chatbot_bp = Blueprint('chatbot', __name__)

# User Data Storage
USER_STATE = {}

# Load language files
try:
    with open('backend/routes/languages/en.json', 'r', encoding='utf-8') as f:
        EN_MESSAGES = json.load(f)
    logging.info(f"Successfully loaded en.json with {len(EN_MESSAGES)} keys.")
except Exception as e:
    logging.error(f"Error loading en.json file: {e}")
    EN_MESSAGES = {}

try:
    with open('backend/routes/languages/ms.json', 'r', encoding='utf-8') as f:
        MS_MESSAGES = json.load(f)
    logging.info(f"Successfully loaded ms.json with {len(MS_MESSAGES)} keys.")
except Exception as e:
    logging.error(f"Error loading ms.json file: {e}")
    MS_MESSAGES = {}

try:
    with open('backend/routes/languages/zh.json', 'r', encoding='utf-8') as f:
        ZH_MESSAGES = json.load(f)
    logging.info(f"Successfully loaded zh.json with {len(ZH_MESSAGES)} keys.")
except Exception as e:
    logging.error(f"Error loading zh.json file: {e}")
    ZH_MESSAGES = {}

LANGUAGE_OPTIONS = {'en': EN_MESSAGES, 'ms': MS_MESSAGES, 'zh': ZH_MESSAGES}

STEP_CONFIG = {
    'choose_language': {
        'message': "choose_language_message",
        'next_step': 'get_name',
        'validator': lambda x, user_data=None: x in ['1', '2', '3']
    },
    'get_name': {
        'message': 'name_message',
        'next_step': 'get_age',
        'validator': lambda x, user_data=None: x.replace(' ', '').isalpha()
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


def process_user_input(current_step, user_data, message_body, language_code):
    logging.debug(f"Processing input for step: {current_step} with message: {message_body}")
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
        data = request.get_json()
        logging.debug(f"Full incoming request: {data}")
        phone_number = data['entry'][0]['changes'][0]['value']['contacts'][0]['wa_id']
        message_body = data['entry'][0]['changes'][0]['value']['messages'][0]['text']['body'].strip().lower()
        
        if message_body == 'restart':
            USER_STATE[phone_number] = {'current_step': 'choose_language'}
            message = get_message('choose_language', 'en')
            logging.info(f"Sending language selection message to {phone_number}: {message}")
            send_whatsapp_message(phone_number, message)
            return jsonify({"status": "success"}), 200

        if phone_number not in USER_STATE:
            USER_STATE[phone_number] = {'current_step': 'choose_language'}

        user_data = USER_STATE[phone_number]
        current_step = user_data.get('current_step', 'choose_language')

        logging.info(f"Current step for {phone_number}: {current_step}")
        logging.info(f"User data for {phone_number}: {user_data}")
        
        if current_step == 'choose_language' and message_body in ['1', '2', '3']:
            user_data['language_code'] = ['en', 'ms', 'zh'][int(message_body) - 1]
            logging.info(f"User selected language: {user_data['language_code']}")
            user_data['current_step'] = STEP_CONFIG['choose_language']['next_step']

        step_info = STEP_CONFIG.get(current_step)
        
        if not step_info['validator'](message_body, user_data):
            message = get_message(current_step, user_data.get('language_code', 'en'))
            logging.info(f"Validation failed for step '{current_step}' with message body '{message_body}'. Sending message: {message}")
            send_whatsapp_message(phone_number, message)
            return jsonify({"status": "failed"}), 400

        process_user_input(current_step, user_data, message_body, user_data.get('language_code', 'en'))
        user_data['current_step'] = step_info['next_step']

        if user_data['current_step'] == 'process_completion':
            logging.info(f"Handling process completion for {phone_number}")
            return handle_process_completion(phone_number, user_data)

        message = get_message(user_data['current_step'], user_data.get('language_code', 'en'))
        logging.info(f"Sending next step message to {phone_number}: {message}")
        send_whatsapp_message(phone_number, message)
        return jsonify({"status": "success"}), 200

    except Exception as e:
        logging.error(f"Error in process_message: {e}")
        return jsonify({"status": "error"}), 500

def handle_process_completion(phone_number, user_data):
    calculation_results = calculate_refinance_savings(user_data['original_loan_amount'], user_data['original_loan_tenure'], user_data['current_repayment'])
    if calculation_results.get('error'):
        send_whatsapp_message(phone_number, 'Calculation error occurred.')
        return jsonify({"status": "error"}), 500
    
    summary_messages = prepare_summary_messages(user_data, calculation_results, user_data.get('language_code', 'en'))
    for message in summary_messages:
        send_whatsapp_message(phone_number, message)
    
    update_database(phone_number, user_data, calculation_results)
    return jsonify({"status": "success"}), 200


def prepare_summary_messages(user_data, calculation_results, language_code):
    """Prepare summary messages to be sent as plain text to the user in their preferred language."""
    
    summary_message_1 = f"{get_message('summary_title_1', language_code)}\n\n" + get_message('summary_content_1', language_code).format(
        current_repayment=f"{user_data['current_repayment']:.2f}",
        new_repayment=f"{calculation_results['new_monthly_repayment']:.2f}",
        monthly_savings=f"{calculation_results['monthly_savings']:.2f}",
        yearly_savings=f"{calculation_results['yearly_savings']:.2f}",
        lifetime_savings=f"{calculation_results['lifetime_savings']:.2f}"
    )

    summary_message_2 = f"{get_message('summary_title_2', language_code)}\n\n" + get_message('summary_content_2', language_code).format(
        monthly_savings=f"{calculation_results['monthly_savings']:.2f}",
        yearly_savings=f"{calculation_results['yearly_savings']:.2f}",
        lifetime_savings=f"{calculation_results['lifetime_savings']:.2f}",
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