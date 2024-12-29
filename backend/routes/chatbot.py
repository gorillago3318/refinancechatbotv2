# Keep existing logging setup at the top
import logging

# System imports
import json
import traceback
import os
import pytz

# Flask imports
from flask import Blueprint, request, jsonify

# Set up Blueprint
chatbot_bp = Blueprint('chatbot', __name__)

# Custom project imports
from backend.utils.calculation import calculate_refinance_savings
from backend.utils.whatsapp import send_whatsapp_message
from backend.models import User, Lead, ChatflowTemp, ChatLog
from backend.extensions import db
import openai  # Correctly import the openai module
from backend.utils.presets import get_preset_response
from datetime import datetime

MYT = pytz.timezone('Asia/Kuala_Lumpur')  # Malaysia timezone

# Logging setup
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("debug.log")
    ]
)

PROMPTS = {
    'en': {
        'choose_language': "🎉 Welcome to FinZo AI — Your Smart Refinancing Assistant! 🤖\n\n💸 Discover Your Savings Potential – Instantly estimate how much you could save by refinancing your home loan.\n💡 Expert Guidance at Your Fingertips – Get quick answers to your refinancing and home loan questions.\n🔄 Simple Restart – Type 'restart' anytime to start over.\n\n👉 Let’s get started! Please select your preferred language:\n\n🌐 Choose Language:\n1️⃣ English \n2️⃣ Bahasa Malaysia \n3️⃣ 中文 (Chinese)",
        'get_name': "📝 *Step 1: Enter Your Name* \n\nPlease enter your *full name*.\n\n💡 Example: John Doe",
        'get_loan_amount': "💸 *Step 2: Enter Your Loan Amount* \n\nPlease enter the *original loan amount*.\n\n💡 Example: 250000",
        'get_loan_tenure': "📆 *Step 3: Enter Your Loan Tenure* \n\nPlease enter the *loan tenure* in years.\n\n💡 Example: 30",
        'get_monthly_repayment': "💳 *Step 4: Enter Your Monthly Repayment* \n\nPlease enter your *current monthly repayment*.\n\n💡 Example: 2500",
        'thank_you': "🎉 Thank you! Your details have been captured. We will calculate your savings and follow up shortly."    
    }
}

openai.api_key = os.getenv("OPENAI_API_KEY").strip()
# ✅ Add routes (Example Route)
@chatbot_bp.route('/test', methods=['GET'])
def test():
    return jsonify({"message": "Chatbot BP is working!"}), 200

def validate_language_choice(x, user_data=None):
    """ Validate that user input is 1, 2, or 3 for language selection. """
    return x in ['1', '2', '3']

def validate_name(x, user_data=None):
    """ Validate that the name contains only letters and spaces. """
    return x.replace(' ', '').isalpha()

def validate_loan_amount(x, user_data=None):
    """ Validate that the loan amount is a numeric value. """
    return x.isdigit()

def validate_loan_tenure(x, user_data=None):
    """ Validate that the loan tenure is a number between 1 and 40 years. """
    return x.isdigit() and 1 <= int(x) <= 40

def validate_monthly_repayment(x, user_data=None):
    """ Validate that the monthly repayment is a numeric value. """
    return x.isdigit()

def validate_process_completion(x, user_data=None):
    """ Always return True for process completion. """
    return True


STEP_CONFIG = {
    'choose_language': {
        'message': "choose_language_message",
        'next_step': 'get_name',
        'validator': validate_language_choice
    },
    'get_name': {
        'message': 'name_message',
        'next_step': 'get_loan_amount',
        'validator': validate_name
    },
    'get_loan_amount': {
        'message': 'loan_amount_message',
        'next_step': 'get_loan_tenure',
        'validator': validate_loan_amount
    },
    'get_loan_tenure': {
        'message': 'loan_tenure_message',
        'next_step': 'get_monthly_repayment',
        'validator': validate_loan_tenure
    },
    'get_monthly_repayment': {
        'message': 'repayment_message',
        'next_step': 'process_completion',
        'validator': validate_monthly_repayment
    },
    'process_completion': {
        'message': 'completion_message',
        'next_step': None,
        'validator': validate_process_completion
    }
}

def delete_chatflow_data(phone_number):
    """Delete all chatflow data for a specific phone number."""
    ChatflowTemp.query.filter_by(phone_number=phone_number).delete()
    db.session.commit()

def process_user_input(current_step, user_data, message_body):
    """Process user input and store it in ChatflowTemp with separate columns."""
    data_to_update = {}

    if current_step == 'choose_language':
        language_mapping = {'1': 'en', '2': 'ms', '3': 'zh'}
        if message_body in language_mapping:
            data_to_update['language_code'] = language_mapping[message_body]
            user_data.language_code = language_mapping[message_body]
        else:
            logging.error(f"❌ Invalid language selection: {message_body}")
            user_data.language_code = 'en'

    elif current_step == 'get_name':
        data_to_update['name'] = message_body.title()

    elif current_step == 'get_loan_amount':
        data_to_update['original_loan_amount'] = float(message_body)

    elif current_step == 'get_loan_tenure':
        data_to_update['original_loan_tenure'] = int(message_body)

    elif current_step == 'get_monthly_repayment':
        data_to_update['current_repayment'] = float(message_body)

    for key, value in data_to_update.items():
        setattr(user_data, key, value)

    next_step = STEP_CONFIG.get(current_step, {}).get('next_step')
    if next_step:
        user_data.current_step = next_step

    db.session.commit()
    logging.info(f"✅ Updated step for user to {user_data.current_step}")
    return jsonify({"status": "success"}), 200


LANGUAGE_OPTIONS = {
    'en': {
        'choose_language_message': "🎉 Welcome to FinZo AI — Your Smart Refinancing Assistant!",
        'name_message': "📝 Enter Your Name.",
        'loan_amount_message': "💸 Enter Loan Amount.",
        'loan_tenure_message': "📆 Enter Loan Tenure.",
        'repayment_message': "💳 Enter Monthly Repayment.",
        'completion_message': "🎉 Thank you! Your details have been captured."
    },
    'ms': {
        'choose_language_message': "🎉 Selamat datang ke FinZo AI — Pembantu Pintar Anda!",
        'name_message': "📝 Masukkan Nama Anda.",
        'loan_amount_message': "💸 Masukkan Jumlah Pinjaman.",
        'loan_tenure_message': "📆 Masukkan Tempoh Pinjaman.",
        'repayment_message': "💳 Masukkan Bayaran Bulanan.",
        'completion_message': "🎉 Terima kasih! Maklumat anda telah disimpan."
    },
    'zh': {
        'choose_language_message': "🎉 欢迎使用 FinZo AI — 您的智能助手!",
        'name_message': "📝 输入您的姓名.",
        'loan_amount_message': "💸 输入贷款金额.",
        'loan_tenure_message': "📆 输入贷款期限.",
        'repayment_message': "💳 输入每月还款金额.",
        'completion_message': "🎉 谢谢！您的详细信息已被记录。"
    }
}

def get_message(key, language_code):
    """ Retrieve a message from the appropriate language file. """
    try:
        if language_code in ['1', '2', '3']:
            language_code = {'1': 'en', '2': 'ms', '3': 'zh'}[language_code]

        if language_code in LANGUAGE_OPTIONS:
            message = LANGUAGE_OPTIONS[language_code].get(key, 'Message not found')
        else:
            logging.error(f"Language '{language_code}' is not found in LANGUAGE_OPTIONS.")
            return 'Message not found'

    except Exception as e:
        logging.error(f"❌ Error in get_message: {e}")
        logging.error(f"Traceback: {traceback.format_exc()}")
        message = 'Message not found'

    return message

def delete_chatflow_data(phone_number):
    """Delete all chatflow data for a specific phone number."""
    ChatflowTemp.query.filter_by(phone_number=phone_number).delete()
    db.session.commit()

def process_user_input(current_step, user_data, message_body):
    """Process user input and store it in ChatflowTemp with separate columns."""
    data_to_update = {}

    if current_step == 'choose_language':
        language_mapping = {'1': 'en', '2': 'ms', '3': 'zh'}
        if message_body in language_mapping:
            data_to_update['language_code'] = language_mapping[message_body]
            user_data.language_code = language_mapping[message_body]
        else:
            logging.error(f"❌ Invalid language selection: {message_body}")
            user_data.language_code = 'en'

    elif current_step == 'get_name':
        data_to_update['name'] = message_body.title()

    elif current_step == 'get_loan_amount':
        data_to_update['original_loan_amount'] = float(message_body)

    elif current_step == 'get_loan_tenure':
        data_to_update['original_loan_tenure'] = int(message_body)

    elif current_step == 'get_monthly_repayment':
        data_to_update['current_repayment'] = float(message_body)

    for key, value in data_to_update.items():
        setattr(user_data, key, value)

    next_step = STEP_CONFIG.get(current_step, {}).get('next_step')
    if next_step:
        user_data.current_step = next_step

    db.session.commit()
    logging.info(f"✅ Updated step for user to {user_data.current_step}")
    return jsonify({"status": "success"}), 200

@chatbot_bp.route('/process_message', methods=['POST'])
def process_message():
    try:
        data = request.get_json()
        phone_number = data['entry'][0]['changes'][0]['value']['contacts'][0]['wa_id']
        message_body = data['entry'][0]['changes'][0]['value']['messages'][0]['text']['body'].strip().lower()

        logging.info(f"💎 Incoming message from {phone_number}: {message_body}")

        # 🔥 Step 1: Get ChatflowTemp Data
        user_data = db.session.query(ChatflowTemp).filter_by(phone_number=phone_number).first()

        # 🔥 Step 2: If no user data exists, create new entry for this phone
        if not user_data:
            user_data = ChatflowTemp(
                phone_number=phone_number, 
                current_step='choose_language', 
                language_code='en', 
                mode='flow'  # ✅ Set default mode to 'flow'
            )
            db.session.add(user_data)
            db.session.commit()
            
            # Send direct language prompt instead of welcome message
            message = "🌐 Choose Language:\n1️⃣ English \n2️⃣ Bahasa Malaysia \n3️⃣ 中文 (Chinese)"
            send_whatsapp_message(phone_number, message)
            
            return jsonify({"status": "success"}), 200

        # 🔥 Step 3: Handle "restart" command (reset the entire flow)
        if message_body == 'restart':
            logging.info(f"🔄 Restarting flow for user {phone_number}")
            user_data.current_step = 'choose_language'
            user_data.mode = 'flow'
            user_data.name = None
            user_data.original_loan_amount = None
            user_data.original_loan_tenure = None
            user_data.current_repayment = None
            db.session.commit()

            # Send language selection prompt again
            message = "🌐 Choose Language:\n1️⃣ English \n2️⃣ Bahasa Malaysia \n3️⃣ 中文 (Chinese)"
            send_whatsapp_message(phone_number, message)
            
            return jsonify({"status": "success"}), 200

        # 🔥 Step 4: Get Current Step and Process It
        current_step = user_data.current_step or 'choose_language'
        step_info = STEP_CONFIG.get(current_step)

        # 🔥 Step 5: Validate user input for the current step
        if not step_info['validator'](message_body, user_data):
            message = get_message(step_info['message'], user_data.language_code or 'en')
            send_whatsapp_message(phone_number, message)
            return jsonify({"status": "failed"}), 400

        # 🔥 Step 6: Process the user input
        process_user_input(current_step, user_data, message_body)
        
        # 🔥 Step 7: If process is complete, trigger process completion logic
        if step_info['next_step'] == 'process_completion':
            return handle_process_completion(phone_number)

        # 🔥 Step 8: Move to the next step and send the next message
        user_language_code = user_data.language_code or 'en'
        message = get_message(step_info['next_step'], user_language_code)
        send_whatsapp_message(phone_number, message)
        
        return jsonify({"status": "success"}), 200

    except Exception as e:
        logging.error(f"❌ Error in process_message: {str(e)}")
        logging.error(f"Traceback: {traceback.format_exc()}")
        db.session.rollback()
        return jsonify({"status": "error"}), 500

def handle_process_completion(phone_number):
    """ Handles the completion of the process and calculates refinance savings. """
    
    try:
        user_data = db.session.query(ChatflowTemp).filter_by(phone_number=phone_number).first()
        
        if not user_data:
            logging.error(f"❌ No user_data found for phone: {phone_number}")
            return jsonify({"status": "error", "message": "No user data found"}), 404

        calculation_results = calculate_refinance_savings(
            user_data.original_loan_amount, 
            user_data.original_loan_tenure, 
            user_data.current_repayment
        )

        if not calculation_results:
            logging.error(f"❌ Calculation failed for phone: {phone_number}")
            return jsonify({"status": "error", "message": "Calculation failed"}), 500

        if calculation_results.get('monthly_savings', 0) <= 0:
            message = (
                "Thank you for using FinZo AI! Your current loan rates are already in great shape. "
                "We’ll be in touch if better offers become available.\n\n"
                "📞 Contact admin at wa.me/60167177813 for help or questions!"
            )
            send_whatsapp_message(phone_number, message)
            user_data.mode = 'query'
            db.session.commit()
            return jsonify({"status": "success"}), 200

        summary_messages = prepare_summary_messages(user_data, calculation_results, user_data.language_code or 'en')
        for message in summary_messages:
            send_whatsapp_message(phone_number, message)

        send_new_lead_to_admin(phone_number, user_data, calculation_results)
        update_database(phone_number, user_data, calculation_results)
        user_data.mode = 'query'
        db.session.commit()

        return jsonify({"status": "success"}), 200

    except Exception as e:
        logging.error(f"❌ Error in handle_process_completion: {str(e)}")
        db.session.rollback()
        return jsonify({"status": "error", "message": "Something went wrong"}), 500

# Map numbers to language codes
LANGUAGE_MAP = {'1': 'en', '2': 'ms', '3': 'zh'}

LANGUAGE_OPTIONS = {
    'en': {
        'choose_language_message': "🎉 Welcome to FinZo AI — Your Smart Refinancing Assistant!",
        'name_message': "📝 Enter Your Name.",
        'loan_amount_message': "💸 Enter Loan Amount.",
        'loan_tenure_message': "📆 Enter Loan Tenure.",
        'repayment_message': "💳 Enter Monthly Repayment.",
        'completion_message': "🎉 Thank you! Your details have been captured.",
        'summary_title_1': "📊 Refinance Savings Summary",
        'summary_content_1': "Your current repayment is RM {current_repayment:.2f}. With refinancing, your new repayment could be RM {new_repayment:.2f}, saving you RM {monthly_savings:.2f} per month, RM {yearly_savings:.2f} yearly, and RM {lifetime_savings:.2f} over the lifetime of the loan.",
        'summary_title_2': "📊 Extended Savings Overview",
        'summary_content_2': "By refinancing, you could save RM {monthly_savings:.2f} per month, RM {yearly_savings:.2f} yearly, and RM {lifetime_savings:.2f} over the lifetime, equivalent to reducing {years_saved} years and {months_saved} months of payments.",
        'summary_title_3': "💬 Next Steps",
        'summary_content_3': "Contact us directly via WhatsApp for assistance: {whatsapp_link}"
    }
}

def prepare_summary_messages(user_data, calculation_results, language_code):
    """ Prepares the summary messages to be sent to the user. """
    
    summary_message_1 = f"{get_message('summary_title_1', language_code)}\n\n" + get_message('summary_content_1', language_code).format(
        current_repayment=getattr(user_data, 'current_repayment', 0.0),
        new_repayment=calculation_results.get('new_monthly_repayment', 0.0),
        monthly_savings=calculation_results.get('monthly_savings', 0.0),
        yearly_savings=calculation_results.get('yearly_savings', 0.0),
        lifetime_savings=calculation_results.get('lifetime_savings', 0.0)
    )

    summary_message_2 = f"{get_message('summary_title_2', language_code)}\n\n" + get_message('summary_content_2', language_code).format(
        monthly_savings=calculation_results.get('monthly_savings', 0.0),
        yearly_savings=calculation_results.get('yearly_savings', 0.0),
        lifetime_savings=calculation_results.get('lifetime_savings', 0.0),
        years_saved=calculation_results.get('years_saved', 0),
        months_saved=calculation_results.get('months_saved', 0)
    )

    summary_message_3 = f"{get_message('summary_title_3', language_code)}\n\n" + get_message('summary_content_3', language_code).format(
        whatsapp_link="https://wa.me/60167177813"
    )

    return [summary_message_1, summary_message_2, summary_message_3]

def prepare_summary_messages(user_data, calculation_results, language_code):
    """ Prepares the summary messages to be sent to the user. """
    
    summary_message_1 = f"{get_message('summary_title_1', language_code)}\n\n" + get_message('summary_content_1', language_code).format(
        current_repayment=getattr(user_data, 'current_repayment', 0.0),
        new_repayment=calculation_results.get('new_monthly_repayment', 0.0),
        monthly_savings=calculation_results.get('monthly_savings', 0.0),
        yearly_savings=calculation_results.get('yearly_savings', 0.0),
        lifetime_savings=calculation_results.get('lifetime_savings', 0.0)
    )

    summary_message_2 = f"{get_message('summary_title_2', language_code)}\n\n" + get_message('summary_content_2', language_code).format(
        monthly_savings=calculation_results.get('monthly_savings', 0.0),
        yearly_savings=calculation_results.get('yearly_savings', 0.0),
        lifetime_savings=calculation_results.get('lifetime_savings', 0.0),
        years_saved=calculation_results.get('years_saved', 0),
        months_saved=calculation_results.get('months_saved', 0)
    )

    summary_message_3 = f"{get_message('summary_title_3', language_code)}\n\n" + get_message('summary_content_3', language_code).format(
        whatsapp_link="https://wa.me/60167177813"
    )

    return [summary_message_1, summary_message_2, summary_message_3]

def update_database(phone_number, user_data, calculation_results):
    try:
        user = User.query.filter_by(wa_id=phone_number).first()
        if not user:
            user = User(
                wa_id=phone_number,
                phone_number=phone_number,
                name=getattr(user_data, 'name', 'Unnamed User')
            )
            db.session.add(user)
            db.session.flush()

        lead = Lead(
            user_id=user.id,
            phone_number=user.phone_number,
            name=getattr(user_data, 'name', 'Unnamed Lead'),
            original_loan_amount=getattr(user_data, 'original_loan_amount', 0.0),
            original_loan_tenure=getattr(user_data, 'original_loan_tenure', 0),
            current_repayment=getattr(user_data, 'current_repayment', 0.0),
            new_repayment=calculation_results.get('new_monthly_repayment', 0.0),
            monthly_savings=calculation_results.get('monthly_savings', 0.0),
            yearly_savings=calculation_results.get('yearly_savings', 0.0),
            total_savings=calculation_results.get('lifetime_savings', 0.0),
            years_saved=calculation_results.get('years_saved', 0)
        )

        db.session.add(lead)
        db.session.commit()
        logging.info(f"✅ Database updated successfully for user {phone_number}")

    except Exception as e:
        logging.error(f"❌ Error updating database for {phone_number}: {str(e)}")
        db.session.rollback()


def send_new_lead_to_admin(phone_number, user_data, calculation_results):
    admin_number = os.getenv('ADMIN_PHONE_NUMBER')
    if not admin_number:
        logging.error("ADMIN_PHONE_NUMBER not set in environment variables.")
        return
    
    message = (
        f"📢 New Lead Alert! 📢\n\n"
        f"👤 Name: {getattr(user_data, 'name', 'Unknown')}\n"
        f"💰 Current Loan Amount: RM {getattr(user_data, 'original_loan_amount', 'N/A')}\n"
        f"📅 Current Tenure: {getattr(user_data, 'original_loan_tenure', 'N/A')} years\n"
        f"📉 Current Repayment: RM {getattr(user_data, 'current_repayment', 'N/A')}\n"
        f"📈 New Repayment: RM {calculation_results.get('new_monthly_repayment', 'N/A')}\n"
        f"💸 Monthly Savings: RM {calculation_results.get('monthly_savings', 'N/A')}\n"
        f"💰 Yearly Savings: RM {calculation_results.get('yearly_savings', 'N/A')}\n"
        f"🎉 Total Savings: RM {calculation_results.get('lifetime_savings', 'N/A')}\n"
        f"🕒 Years Saved: {calculation_results.get('years_saved', 'N/A')} years\n\n"
        f"📱 Whatsapp ID: https://wa.me/{phone_number}"
    )

    send_whatsapp_message(admin_number, message)

def handle_gpt_query(question, user_data, phone_number):
    """Handles GPT query requests confined to refinance and home loan topics only."""
    current_time = datetime.datetime.now()

    try:
        # 🟢 Step 1: Check for a preset response for the question
        response = get_preset_response(question, user_data.language_code or 'en')
        
        if response:
            logging.info(f"✅ Preset response found for query: {question}")
            message = response
        else:
            # 🟢 Step 2: Call OpenAI GPT-3.5-turbo with strict topic guidelines
            logging.info(f"❌ No preset found. Querying OpenAI GPT for: {question}")
            system_prompt = (
                "You are a helpful assistant focused only on refinance and home loan topics. "
                "Respond strictly about home loans, refinancing, mortgage rates, eligibility, payments, and savings options. "
                "Avoid unrelated topics and politely redirect users to stay focused on these subjects."
            )
            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": question}
                ]
            )
            message = response.choices[0].message.content
            logging.info(f"✅ GPT response received for user {phone_number}")

        # 🟢 Log the GPT Query into ChatLog table
        log_gpt_query(phone_number, question, message)  # Pass phone number instead of user_id

    except Exception as e:
        logging.error(f"❌ Error while handling GPT query for {phone_number}: {str(e)}")
        message = (
            "We're currently experiencing issues processing your request. "
            "Please try again later or contact our admin for assistance: wa.me/60167177813"
        )

    try:
        send_whatsapp_message(phone_number, message)
    except Exception as e:
        logging.error(f"❌ Error sending message to user {phone_number}: {str(e)}")


def log_chat(phone_number, user_message, bot_message):
    """Logs regular chats into ChatLog table with valid user_id."""
    try:
        # 🟢 Ensure phone_number is always a string
        phone_number = str(phone_number)

        # 🟢 Fetch or Create User
        user = User.query.filter_by(phone_number=phone_number).first()
        if not user:
            user = User(
                wa_id=phone_number,
                phone_number=phone_number,
                name="Unknown User"
            )
            db.session.add(user)
            db.session.flush()  # Get user ID before commit

        # 🟢 Log the Chat
        chat_log = ChatLog(  # Correct Model Name
            user_id=user.id,
            message=f"User: {user_message}\nBot: {bot_message}"
        )
        db.session.add(chat_log)
        db.session.commit()
        logging.info(f"✅ Chat logged for user {user.phone_number}")

    except Exception as e:
        logging.error(f"❌ Error while logging chat: {str(e)}")
        db.session.rollback()

def log_gpt_query(phone_number, user_message, bot_response):
    """Logs the GPT query to the ChatLog table with user_id properly set."""
    try:
        # 🟢 Step 1: Fetch or Create User
        user = User.query.filter_by(phone_number=phone_number).first()
        if not user:
            # Create user if it doesn't exist
            user = User(
                wa_id=phone_number,
                phone_number=phone_number,
                name="Unknown User"
            )
            db.session.add(user)
            db.session.flush()  # Ensures user.id is available before commit

        # 🟢 Step 2: Insert ChatLog with correct user_id
        chat_log = ChatLog(
            user_id=user.id,  # Use valid user ID
            message=f"User: {user_message}\nBot: {bot_response}"
        )
        db.session.add(chat_log)
        db.session.commit()
        logging.info(f"✅ GPT query logged for user {user.phone_number}")

    except Exception as e:
        logging.error(f"❌ Error logging GPT query for {phone_number}: {str(e)}")
        db.session.rollback()
