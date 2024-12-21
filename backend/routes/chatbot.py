# Keep existing logging setup at the top
import logging

# System imports
import json
import datetime
import traceback
import os

# Flask imports
from flask import Blueprint, request, jsonify

# Set up Blueprint
chatbot_bp = Blueprint('chatbot', __name__)

# Custom project imports
from backend.utils.calculation import calculate_refinance_savings
from backend.utils.whatsapp import send_whatsapp_message
from backend.models import User, Lead, ChatflowTemp, ChatLog  # 🟢 Removed the second 'db' import
from backend.extensions import db  # ✅ Keep only this import for 'db'
from openai import OpenAI
from backend.utils.presets import get_preset_response

# Initialize OpenAI client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

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

def validate_age(x, user_data=None):
    """ Validate that the age is a number between 18 and 70. """
    return x.isdigit() and 18 <= int(x) <= 70

def validate_loan_amount(x, user_data=None):
    """ Validate that the loan amount is a numeric value. """
    return x.isdigit()

def validate_loan_tenure(x, user_data=None):
    """ Validate that the loan tenure is a number between 1 and 40 years. """
    return x.isdigit() and 1 <= int(x) <= 40

def validate_monthly_repayment(x, user_data=None):
    """ Validate that the monthly repayment is a numeric value. """
    return x.isdigit()

def validate_interest_rate(x, user_data=None):
    """ Validate that the interest rate is either 'skip' or a float between 3 and 10. """
    return x.lower() == 'skip' or (x.replace('.', '', 1).isdigit() and 3 <= float(x) <= 10)

def validate_remaining_tenure(x, user_data=None):
    """ 
    Validate that the remaining tenure is either 'skip' or less than the original loan tenure. 
    Defaults to True if `original_loan_tenure` is missing. 
    """
    if x.lower() == 'skip':
        return True
    if x.isdigit():
        original_tenure = getattr(user_data, 'original_loan_tenure', 0)
        return original_tenure and int(x) < original_tenure
    return False

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
        'next_step': 'get_age',
        'validator': validate_name
    },
    'get_age': {
        'message': 'age_message',
        'next_step': 'get_loan_amount',
        'validator': validate_age
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
        'next_step': 'get_interest_rate',
        'validator': validate_monthly_repayment
    },
    'get_interest_rate': {
        'message': 'interest_rate_message',
        'next_step': 'get_remaining_tenure',
        'validator': validate_interest_rate
    },
    'get_remaining_tenure': {
        'message': 'remaining_tenure_message',
        'next_step': 'process_completion',
        'validator': validate_remaining_tenure
    },
    'process_completion': {
        'message': 'completion_message',
        'next_step': None,
        'validator': validate_process_completion
    }
}


from backend.models import ChatflowTemp, db
import json

def delete_chatflow_data(phone_number):
    """Delete all chatflow data for a specific phone number."""
    ChatflowTemp.query.filter_by(phone_number=phone_number).delete()
    db.session.commit()

def process_user_input(current_step, user_data, message_body):
    """Process user input and store it in ChatflowTemp with separate columns."""
    phone_number = user_data.phone_number
    data_to_update = {}

    if current_step == 'choose_language':
        language_mapping = {'1': 'en', '2': 'ms', '3': 'zh'}
        if message_body in language_mapping:
            data_to_update['language_code'] = language_mapping[message_body]
            user_data.language_code = language_mapping[message_body]
        else:
            logging.error(f"❌ Invalid language selection: {message_body}")
            # Fallback to English if an invalid input is provided
            user_data.language_code = 'en'
    
    elif current_step == 'get_name':
        data_to_update['name'] = message_body.title()
    
    elif current_step == 'get_age':
        data_to_update['age'] = int(message_body)
    
    elif current_step == 'get_loan_amount':
        data_to_update['original_loan_amount'] = float(message_body)
    
    elif current_step == 'get_loan_tenure':
        data_to_update['original_loan_tenure'] = int(message_body)
    
    elif current_step == 'get_monthly_repayment':
        data_to_update['current_repayment'] = float(message_body)
    
    elif current_step == 'get_interest_rate' and message_body.lower() != 'skip':
        data_to_update['interest_rate'] = float(message_body)

    elif current_step == 'get_remaining_tenure' and message_body.lower() != 'skip':
        data_to_update['remaining_tenure'] = int(message_body)

    # Store user input in ChatflowTemp
    for key, value in data_to_update.items():
        setattr(user_data, key, value)

    # Update the current step
    next_step = STEP_CONFIG.get(current_step, {}).get('next_step')
    if next_step:
        user_data.current_step = next_step

    # Commit the changes to the database
    db.session.commit()
    
    logging.info(f"✅ Updated step for phone {user_data.phone_number} to {user_data.current_step}")
    return jsonify({"status": "success"}), 200

def get_message(key, language_code):
    """ 
    Retrieve a message from the appropriate language file. 
    Maps 1, 2, 3 to language codes en, ms, zh.
    """
    try:
        if language_code in ['1', '2', '3']:
            language_code = {'1': 'en', '2': 'ms', '3': 'zh'}[language_code]

        step_key = STEP_CONFIG.get(key, {}).get('message', key)

        if language_code in LANGUAGE_OPTIONS:
            message = LANGUAGE_OPTIONS[language_code].get(step_key, 'Message not found')
        else:
            logging.error(f"Language '{language_code}' is not found in LANGUAGE_OPTIONS.")
            return 'Message not found'

    except Exception as e:
        logging.error(f"❌ Error in get_message: {e}")
        logging.error(f"Traceback: {traceback.format_exc()}")
        message = 'Message not found'
    
    return message


# Map numbers to language codes
LANGUAGE_MAP = {'1': 'en', '2': 'ms', '3': 'zh'}

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
            
            message = get_message('choose_language', 'en')
            send_whatsapp_message(phone_number, message)
            
            return jsonify({"status": "success"}), 200

        # 🔥 Step 3: Handle "restart" command (reset the entire flow)
        if message_body == 'restart':
            logging.info(f"🔄 Restarting flow for user {phone_number}")
            user_data.current_step = 'choose_language'
            user_data.mode = 'flow'  # ✅ Reset mode to 'flow'
            user_data.name = None
            user_data.age = None
            user_data.original_loan_amount = None
            user_data.original_loan_tenure = None
            user_data.current_repayment = None
            user_data.interest_rate = None
            user_data.remaining_tenure = None
            db.session.commit()

            message = get_message('choose_language', 'en')
            send_whatsapp_message(phone_number, message)
            
            log_chat(user_data.id, message_body, message)  # ✅ Log the restart command
            return jsonify({"status": "success"}), 200

        # 🔥 Step 4: Check if the user is in "query" mode
        if user_data.mode == 'query':
            logging.info(f"🟢 User {phone_number} is in query mode.")
            
            # 🟢 Call GPT to handle user query
            response = handle_gpt_query(message_body, user_data, phone_number)
            
            # 🟢 Log GPT-related chats only when in query mode
            log_chat(user_data.id, message_body, response)  # ✅ Log GPT conversations only
            
            return jsonify({"status": "success"}), 200

        # 🔥 Step 5: Get Current Step and Process It
        current_step = user_data.current_step or 'choose_language'
        step_info = STEP_CONFIG.get(current_step)

        # 🔥 Step 6: Validate user input for the current step
        if not step_info['validator'](message_body, user_data):
            message = get_message(current_step, user_data.language_code or 'en')
            send_whatsapp_message(phone_number, message)
            return jsonify({"status": "failed"}), 400

        # 🔥 Step 7: Process the user input
        process_user_input(current_step, user_data, message_body)
        
        # 🔥 Step 8: If process is complete, trigger process completion logic
        if step_info['next_step'] == 'process_completion':
            return handle_process_completion(phone_number)

        # 🔥 Step 9: Move to the next step and send the next message
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
        # 🟢 Step 1: Get the user's data from ChatflowTemp
        user_data = db.session.query(ChatflowTemp).filter_by(phone_number=phone_number).first()
        
        if not user_data:
            logging.error(f"❌ No user_data found for phone: {phone_number}")
            return jsonify({"status": "error", "message": "No user data found"}), 404

        # 🟢 Step 2: Calculate refinance savings using the user's data
        calculation_results = calculate_refinance_savings(
            user_data.original_loan_amount, 
            user_data.original_loan_tenure, 
            user_data.current_repayment
        )

        if not calculation_results:
            logging.error(f"❌ Calculation failed for phone: {phone_number}")
            return jsonify({"status": "error", "message": "Calculation failed"}), 500
        
        # 🟢 Step 3: If no savings are available, send a message and return early
        if calculation_results.get('monthly_savings', 0) <= 0:
            message = (
                "Thank you for using FinZo AI! Our analysis shows that your current loan rates are already in great shape. "
                "We’ll be in touch if better offers become available.\n\n"
                "📞 Need help or have questions? Contact our admin directly at wa.me/60167177813.\n"
                "💬 Want to explore refinancing options or have questions on home loans? Our FinZo AI support is ready to assist you at any time!"
            )
            send_whatsapp_message(phone_number, message)
            
            # Update user mode in ChatflowTemp to "query"
            user_data.mode = 'query'
            db.session.commit()
            logging.info(f"✅ User {phone_number} switched to query mode after no savings found.")
            return jsonify({"status": "success"}), 200

        # 🟢 Step 4: If savings are available, send a summary of the savings
        summary_messages = prepare_summary_messages(user_data, calculation_results, user_data.language_code or 'en')
        for message in summary_messages:
            send_whatsapp_message(phone_number, message)

        # 🟢 Step 5: Send new lead alert to admin
        send_new_lead_to_admin(phone_number, user_data, calculation_results)
        
        # 🟢 Step 6: Update the Lead in the database
        update_database(phone_number, user_data, calculation_results)
        
        # 🟢 Update the user to "query" mode in ChatflowTemp
        user_data.mode = 'query'
        db.session.commit()
        
        logging.info(f"✅ User {phone_number} switched to query mode after summary sent.")
        return jsonify({"status": "success"}), 200

    except Exception as e:
        logging.error(f"❌ Error in handle_process_completion for phone: {phone_number}. Error: {str(e)}")
        db.session.rollback()
        return jsonify({"status": "error", "message": "Something went wrong"}), 500

def prepare_summary_messages(user_data, calculation_results, language_code):
    """ Prepares the summary messages to be sent to the user. """
    
    # 🟢 Pass raw numbers directly to .format()
    summary_message_1 = f"{get_message('summary_title_1', language_code)}\n\n" + get_message('summary_content_1', language_code).format(
        current_repayment=getattr(user_data, 'current_repayment', 0.0),  # Pass the float directly
        new_repayment=calculation_results.get('new_monthly_repayment', 0.0),  # Pass the float directly
        monthly_savings=calculation_results.get('monthly_savings', 0.0),  # Pass the float directly
        yearly_savings=calculation_results.get('yearly_savings', 0.0),  # Pass the float directly
        lifetime_savings=calculation_results.get('lifetime_savings', 0.0)  # Pass the float directly
    )

    summary_message_2 = f"{get_message('summary_title_2', language_code)}\n\n" + get_message('summary_content_2', language_code).format(
        monthly_savings=calculation_results.get('monthly_savings', 0.0),  # Pass the float directly
        yearly_savings=calculation_results.get('yearly_savings', 0.0),  # Pass the float directly
        lifetime_savings=calculation_results.get('lifetime_savings', 0.0),  # Pass the float directly
        years_saved=calculation_results.get('years_saved', 0),  # Pass as integer
        months_saved=calculation_results.get('months_saved', 0)  # Pass as integer
    )

    summary_message_3 = f"{get_message('summary_title_3', language_code)}\n\n" + get_message('summary_content_3', language_code).format(
        whatsapp_link="https://wa.me/60167177813"
    )

    # 🟢 Return all three summary messages
    return [summary_message_1, summary_message_2, summary_message_3]

def update_database(phone_number, user_data, calculation_results):
    try:
        user = User.query.filter_by(wa_id=phone_number).first()
        if not user:
            user = User(
                wa_id=phone_number,
                phone_number=phone_number,
                name=getattr(user_data, 'name', 'Unnamed User'),
                age=getattr(user_data, 'age', 0)
            )
            db.session.add(user)
            db.session.flush()  # To get user.id

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
    """Handles GPT query requests from users with a limit of 15 questions per 24-hour period."""
    
    GPT_QUERY_LIMIT = 15  # Centralized constant
    current_time = datetime.datetime.now()

    try:
        # 🟢 Step 1: Reset the user's daily query count if 24 hours have passed
        last_question_time = user_data.last_question_time
        query_count = user_data.gpt_query_count or 0  # Default to 0 if None
        
        if last_question_time:
            time_difference = current_time - last_question_time
            if time_difference.total_seconds() > 86400:  # 24 hours = 86400 seconds
                query_count = 0  # Reset daily limit
                logging.info(f"✅ Query count reset for user {phone_number} after 24 hours.")
        
        # 🟢 Step 2: Check if the user has reached the daily limit of 15 questions
        if query_count >= GPT_QUERY_LIMIT:
            send_limit_reached_message(phone_number)
            return

        # 🟢 Step 3: Update the user's query count and last question time
        user_data.gpt_query_count = query_count + 1
        user_data.last_question_time = current_time
        db.session.commit()

        # 🟢 Notify user if they have 10 or 5 queries remaining
        questions_left = GPT_QUERY_LIMIT - user_data.gpt_query_count
        if questions_left in [10, 5]:
            send_remaining_query_notification(phone_number, questions_left)

    except Exception as e:
        logging.error(f"❌ Error updating query count for user {phone_number}: {str(e)}")
        db.session.rollback()  # Rollback to avoid partial commits
        return

    try:
        # 🟢 Step 4: Check for a preset response for the question
        response = get_preset_response(question, user_data.language_code or 'en')
        
        if response:
            logging.info(f"✅ Preset response found for query: {question}")
            message = response
        else:
            # 🟢 Step 5: Call OpenAI GPT-3.5-turbo if no preset response is found
            logging.info(f"❌ No preset found. Querying OpenAI GPT for: {question}")
            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": question}]
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
                name="Unknown User",
                age=0
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
                name="Unknown User",  # Default name if missing
                age=0  # Default age if missing
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

def send_limit_reached_message(phone_number):
    """Send a message to the user that they have reached their daily query limit."""
    message = (
        "🚫 You've reached your daily limit of 15 questions.\n"
        "Your limit will reset in 24 hours. \n\n"
        "💬 Contact admin for urgent help: wa.me/60167177813\n\n"
        "Thank you for using FinZo AI!"
    )
    try:
        send_whatsapp_message(phone_number, message)
    except Exception as e:
        logging.error(f"❌ Error sending limit reached message to {phone_number}: {str(e)}")
        
def send_remaining_query_notification(phone_number, questions_left):
    """Notify the user of how many queries they have left."""
    try:
        message = f"🤖 You have {questions_left} questions remaining today."
        send_whatsapp_message(phone_number, message)
        logging.info(f"✅ Sent query count notification to {phone_number}: {questions_left} questions left")
    except Exception as e:
        logging.error(f"❌ Error sending query count notification to {phone_number}: {str(e)}")


def reset_query_count(user_data):
    """Reset the user's query count and update their last query time."""
    user_data.gpt_query_count = 0
    user_data.last_question_time = datetime.datetime.now()
    db.session.commit()
    logging.info(f"✅ Reset query count for user {user_data.phone_number}")
