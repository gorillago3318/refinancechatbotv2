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

# 🗂️ Load language files
try:
    with open('backend/routes/languages/en.json', 'r', encoding='utf-8') as f:
        EN_MESSAGES = json.load(f)
except Exception as e:
    logging.error(f"❌ Error loading en.json file: {e}")
    EN_MESSAGES = {}

try:
    with open('backend/routes/languages/ms.json', 'r', encoding='utf-8') as f:
        MS_MESSAGES = json.load(f)
except Exception as e:
    logging.error(f"❌ Error loading ms.json file: {e}")
    MS_MESSAGES = {}

try:
    with open('backend/routes/languages/zh.json', 'r', encoding='utf-8') as f:
        ZH_MESSAGES = json.load(f)
except Exception as e:
    logging.error(f"❌ Error loading zh.json file: {e}")
    ZH_MESSAGES = {}

LANGUAGE_OPTIONS = {'en': EN_MESSAGES, 'ms': MS_MESSAGES, 'zh': ZH_MESSAGES}

logging.info(f"🧐 LANGUAGE_OPTIONS keys: {list(LANGUAGE_OPTIONS.keys())}")
logging.info(f"📄 ENGLISH MESSAGES: {list(EN_MESSAGES.keys())}")

# User Data Storage
USER_STATE = {}

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

def get_message(key, language_code):
    try:
        step_key = key  # ✅ Initialize step_key to avoid "not defined" errors
        
        # Check for valid language
        if not language_code:  
            logging.warning(f"❌ Language '{language_code}' is not found. Defaulting to 'en'.")
            language_code = 'en'
        
        if language_code not in LANGUAGE_OPTIONS:
            logging.error(f"Language '{language_code}' is not found in LANGUAGE_OPTIONS. Defaulting to 'en'.")
            language_code = 'en'
        
        # Check if the key is part of step config
        if key in STEP_CONFIG:
            step_key = STEP_CONFIG[key]['message']

        logging.debug(f"🔍 Searching for message with key: '{step_key}' in language: '{language_code}'")

        # Get the message
        message = LANGUAGE_OPTIONS.get(language_code, {}).get(step_key, 'Message not found')
        
        if message == 'Message not found':
            logging.error(f"❌ Missing message for key: '{step_key}' in {language_code} file.")
    except Exception as e:
        logging.error(f"❌ Error in get_message for key '{key}' with language '{language_code}': {e}")
        message = 'Message not found'

    return message

@chatbot_bp.route('/process_message', methods=['POST'])
def process_message():
    try:
        data = request.get_json()
        
        # Extract phone number and message body
        try:
            phone_number = data['entry'][0]['changes'][0]['value']['contacts'][0]['wa_id']
            message_body = data['entry'][0]['changes'][0]['value']['messages'][0]['text']['body']
            message_body = message_body.strip().lower()
            message_body_cleaned = ''.join(filter(str.isdigit, message_body))
            logging.debug(f"☎️ Extracted phone number: {phone_number} | 📨 Message body: '{message_body}'")
        except (KeyError, IndexError, AttributeError) as e:
            logging.error(f"❌ Error extracting phone_number or message_body: {e}", exc_info=True)
            return jsonify({"status": "error", "message": "Invalid request format"}), 400
        
        if message_body == 'restart':
            logging.info(f"🔄 User requested a restart. Resetting state for {phone_number}.")
            USER_STATE[phone_number] = {
                'current_step': 'choose_language',
                'mode': 'active',
                'language_code': 'en',  # ✅ Set to 'en' by default
            }
            message = get_message('choose_language', 'en')  # ✅ Ensuring the language is valid
            send_whatsapp_message(phone_number, message)
            return jsonify({"status": "success"}), 200

        if phone_number not in USER_STATE:
            USER_STATE[phone_number] = {
                'current_step': 'choose_language',
                'mode': 'active',
                'language_code': 'en',  # ✅ Default to 'en'
                'name': None,
                'age': None,
                'original_loan_amount': None,
                'original_loan_tenure': None,
                'current_repayment': None,
                'interest_rate': None,
                'remaining_tenure': None,
            }

        user_data = USER_STATE[phone_number]
        current_step = user_data.get('current_step', 'choose_language')

        # 🟢 Handle the 'choose_language' step
        if current_step == 'choose_language':
            if message_body in ['1', '2', '3']:  # ✅ Check if user selected 1, 2, or 3
                user_data['language_code'] = ['en', 'ms', 'zh'][int(message_body) - 1]  # ✅ Set language code
                user_data['current_step'] = STEP_CONFIG['choose_language']['next_step']  # ✅ Move to the next step
                message = get_message(user_data['current_step'], user_data['language_code'])  # Get message for the next step
                logging.info(f"🌐 Language set to '{user_data['language_code']}' for {phone_number}. Next step: {user_data['current_step']}")
                send_whatsapp_message(phone_number, message)  # Send the next step message
                return jsonify({"status": "success"}), 200
            else:
                message = get_message('choose_language', 'en')  # Resend the language selection message
                logging.warning(f"⚠️ Invalid language selection for {phone_number}: '{message_body}'")
                send_whatsapp_message(phone_number, message)
                return jsonify({"status": "failed"}), 400

        step_info = STEP_CONFIG.get(current_step)
        if not step_info:
            logging.error(f"❌ Step '{current_step}' not found in STEP_CONFIG.")
            send_whatsapp_message(phone_number, "An error occurred. Please try again later.")
            return jsonify({"status": "error"}), 500

        if not step_info['validator'](message_body, user_data):
            message = get_message(current_step, user_data.get('language_code', 'en'))
            send_whatsapp_message(phone_number, message)
            return jsonify({"status": "failed"}), 400
        
        process_user_input(current_step, user_data, message_body, user_data.get('language_code', 'en'))
        user_data['current_step'] = step_info.get('next_step')
        
        message = get_message(user_data['current_step'], user_data.get('language_code', 'en'))
        logging.info(f"📲 Sending message for next step: '{user_data['current_step']}' to {phone_number}")
        send_whatsapp_message(phone_number, message)
        
        return jsonify({"status": "success"}), 200

    except Exception as e:
        logging.error(f"❌ Unexpected error in process_message: {e}", exc_info=True)
        send_whatsapp_message(phone_number, "An unexpected error occurred. Please try again or contact support.")
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

def handle_process_completion(phone_number, user_data):
    try:
        calculation_results = calculate_refinance_savings(
            user_data['original_loan_amount'], 
            user_data['original_loan_tenure'], 
            user_data['current_repayment']
        )

        if calculation_results.get('monthly_savings', 0) <= 0:
            message = (
                "Thank you for using FinZo AI! Our analysis shows that your current loan rates are already in great shape. "
                "We’ll be in touch if better offers become available.\n\n"
                "📞 Need help or have questions? Contact our admin directly at wa.me/60167177813.\n"
                "💬 Want to explore refinancing options or have questions on home loans? Our FinZo AI support is ready to assist you at any time!"
            )
            send_whatsapp_message(phone_number, message)
            user_data['mode'] = 'query'  # Switch user mode to "query"
            return jsonify({"status": "success"}), 200

        summary_messages = prepare_summary_messages(user_data, calculation_results, user_data.get('language_code', 'en'))
        for message in summary_messages:
            send_whatsapp_message(phone_number, message)
        
        send_new_lead_to_admin(phone_number, user_data)
        user_data['mode'] = 'query'  # Switch to "query" mode
        return jsonify({"status": "success"}), 200

    except Exception as e:
        logging.error(f"❌ Error in handle_process_completion for {phone_number}: {str(e)}", exc_info=True)
        return jsonify({"status": "error"}), 500

def prepare_summary_messages(user_data, calculation_results, language_code):
    try:
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
    except Exception as e:
        logging.error(f"❌ Error in prepare_summary_messages: {str(e)}", exc_info=True)
        return []

def update_database(phone_number, user_data, calculation_results):
    try:
        user = User.query.filter_by(wa_id=phone_number).first()
        if not user:
            user = User(
                wa_id=phone_number,
                phone_number=phone_number,
                name=user_data.get('name'),
                age=user_data.get('age')
            )
            db.session.add(user)
            db.session.flush()  # To ensure user_id is available for lead

        lead = Lead(
            user_id=user.id,
            phone_number=user.phone_number,
            name=user_data.get('name', 'Unnamed Lead'),  
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
        logging.error(f"❌ Error updating database for {phone_number}: {str(e)}", exc_info=True)

def send_new_lead_to_admin(phone_number, user_data):
    try:
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
        logging.info(f"📢 Lead alert sent to admin: {admin_number}")
    except Exception as e:
        logging.error(f"❌ Error in send_new_lead_to_admin for {phone_number}: {str(e)}", exc_info=True)

def handle_gpt_query(question, user_data, phone_number):
    try:
        GPT_QUERY_LIMIT = 15
        current_time = datetime.datetime.now()
        last_question_time = user_data.get('last_question_time')

        if last_question_time:
            time_difference = current_time - last_question_time
            if time_difference.total_seconds() > 86400:
                user_data['gpt_query_count'] = 0  # Reset count after 24 hours

        user_data['last_question_time'] = current_time

        if user_data.get('gpt_query_count', 0) >= GPT_QUERY_LIMIT:
            message = (
                "You have reached your daily limit of 15 questions. Your limit will reset in 24 hours. "
                "If you'd like immediate assistance, contact our admin: wa.me/60167177813"
            )
            send_whatsapp_message(phone_number, message)
            return

        user_data['gpt_query_count'] = user_data.get('gpt_query_count', 0) + 1

        response = get_preset_response(question, user_data.get('language_code', 'en'))
        
        if response:
            message = response
        else:
            try:
                response = client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[{"role": "user", "content": question}]
                )
                message = response.choices[0].message.content
            except Exception as e:
                logging.error(f"❌ Error while calling GPT: {str(e)}")
                message = "We're currently experiencing issues. Please try later."

        send_whatsapp_message(phone_number, message)
    except Exception as e:
        logging.error(f"❌ Error in handle_gpt_query for {phone_number}: {str(e)}", exc_info=True)
