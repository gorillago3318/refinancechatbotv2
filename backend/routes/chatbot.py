import logging
import redis  
import json
import datetime
import os  
import urllib.parse
from flask import Blueprint, request, jsonify
from backend.utils.calculation import calculate_refinance_savings
from backend.utils.whatsapp import send_whatsapp_message
from backend.models import User, Lead
from backend.extensions import db
from openai import OpenAI
from backend.utils.presets import get_preset_response

# Set up logging
logging.basicConfig(level=logging.DEBUG)

class RedisManager:
    def __init__(self):
        REDIS_URL = os.getenv("REDIS_URL")
        if REDIS_URL:
            url = urllib.parse.urlparse(REDIS_URL)
            self.client = redis.StrictRedis(
                host=url.hostname, 
                port=url.port, 
                password=url.password, 
                decode_responses=True
            )
        else:
            self.client = redis.StrictRedis(
                host=os.getenv("REDIS_HOST", "localhost"), 
                port=int(os.getenv("REDIS_PORT", 6379)), 
                password=os.getenv("REDIS_PASSWORD", None), 
                decode_responses=True
            )

    def initialize_language_files(self):
        """Load and cache language files in Redis."""
        try:
            for lang in ['en', 'ms', 'zh']:
                if not self.client.exists(f'language:{lang}'):
                    with open(f'backend/routes/languages/{lang}.json', 'r', encoding='utf-8') as f:
                        messages = json.load(f)
                        self.client.set(f'language:{lang}', json.dumps(messages))
        except Exception as e:
            logging.error(f"❌ Error loading language files into Redis: {e}")

    def get_message(self, key, language_code='en'):
        """Get message from Redis by key and language."""
        try:
            language_data = json.loads(self.client.get(f'language:{language_code}'))
            return language_data.get(key, 'Message not found')
        except Exception as e:
            logging.error(f"❌ Error in get_message: {e}")
            return 'Message not found'

class UserStateManager:
    def __init__(self, redis_client):
        self.redis_client = redis_client

    @staticmethod
    def default_state():
        """Return the default user state."""
        return {
            'current_step': 'choose_language',
            'mode': 'active',
            'language_code': 'en',
            'name': None,
            'age': None,
            'original_loan_amount': None,
            'original_loan_tenure': None,
            'current_repayment': None,
            'interest_rate': None,
            'remaining_tenure': None,
        }

    def get_state(self, phone_number):
        """Retrieve the user's state from Redis."""
        user_state = self.redis_client.get(f'user_state:{phone_number}')
        if user_state:
            return json.loads(user_state)
        default_state = self.default_state()
        self.set_state(phone_number, default_state)
        return default_state

    def set_state(self, phone_number, user_state):
        """Update the user's state in Redis."""
        self.redis_client.set(f'user_state:{phone_number}', json.dumps(user_state))

    def process_input(self, current_step, user_data, message_body):
        """Process user input based on current step."""
        input_processors = {
            'get_name': lambda: message_body.title(),
            'get_age': lambda: int(message_body),
            'get_loan_amount': lambda: int(message_body),
            'get_loan_tenure': lambda: int(message_body),
            'get_monthly_repayment': lambda: int(message_body),
            'get_interest_rate': lambda: float(message_body) if message_body.lower() != 'skip' else None,
            'get_remaining_tenure': lambda: int(message_body) if message_body.lower() != 'skip' else None
        }

        if current_step in input_processors:
            field_name = current_step.replace('get_', '')
            user_data[field_name] = input_processors[current_step]()

class ChatbotHandler:
    def __init__(self):
        self.redis_manager = RedisManager()
        self.user_state_manager = UserStateManager(self.redis_manager.client)
        self.openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.redis_manager.initialize_language_files()

    def handle_message(self, phone_number, message_body):
        """Main message handling logic."""
        if message_body == 'restart':
            return self.restart_session(phone_number)

        user_data = self.user_state_manager.get_state(phone_number)
        current_step = user_data.get('current_step', 'choose_language')

        if current_step == 'choose_language' and message_body in ['1', '2', '3']:
            return self.handle_language_selection(phone_number, message_body, user_data)

        self.user_state_manager.process_input(current_step, user_data, message_body)
        self.user_state_manager.set_state(phone_number, user_data)

        message = self.redis_manager.get_message(user_data['current_step'], user_data['language_code'])
        send_whatsapp_message(phone_number, message)
        return jsonify({"status": "success"}), 200

    def handle_language_selection(self, phone_number, message_body, user_data):
        """Handle language selection step."""
        user_data['language_code'] = ['en', 'ms', 'zh'][int(message_body) - 1]
        user_data['current_step'] = 'get_name'
        self.user_state_manager.set_state(phone_number, user_data)
        message = self.redis_manager.get_message('name_message', user_data['language_code'])
        send_whatsapp_message(phone_number, message)
        return jsonify({"status": "success"}), 200

    def restart_session(self, phone_number):
        """Reset user session to initial state."""
        user_data = self.user_state_manager.default_state()
        self.user_state_manager.set_state(phone_number, user_data)
        message = self.redis_manager.get_message('choose_language', 'en')
        send_whatsapp_message(phone_number, message)
        return jsonify({"status": "success"}), 200

    def handle_gpt_query(self, question, user_data, phone_number):
        """Handle GPT queries with rate limiting."""
        try:
            if not self._check_query_limit(user_data):
                message = "You have reached your daily limit of 15 questions. Your limit will reset in 24 hours."
                send_whatsapp_message(phone_number, message)
                return

            response = get_preset_response(question, user_data.get('language_code', 'en'))
            if not response:
                response = self.openai_client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[{"role": "user", "content": question}]
                )
                message = response.choices[0].message.content
            send_whatsapp_message(phone_number, message)
        except Exception as e:
            logging.error(f"❌ Error in handle_gpt_query: {e}")

    def _check_query_limit(self, user_data):
        """Check if user has exceeded daily query limit."""
        GPT_QUERY_LIMIT = 15
        current_time = datetime.datetime.now()
        last_question_time = user_data.get('last_question_time')

        if last_question_time:
            time_difference = current_time - last_question_time
            if time_difference.total_seconds() > 86400:
                user_data['gpt_query_count'] = 0

        user_data['last_question_time'] = current_time
        user_data['gpt_query_count'] = user_data.get('gpt_query_count', 0) + 1
        
        return user_data['gpt_query_count'] <= GPT_QUERY_LIMIT

# Initialize Flask Blueprint and handler
chatbot_bp = Blueprint('chatbot', __name__)
chatbot_handler = ChatbotHandler()

@chatbot_bp.route('/process_message', methods=['POST'])
def process_message():
    try:
        data = request.get_json()
        phone_number = data['entry'][0]['changes'][0]['value']['contacts'][0]['wa_id']
        message_body = data['entry'][0]['changes'][0]['value']['messages'][0]['text']['body'].strip().lower()
        return chatbot_handler.handle_message(phone_number, message_body)
    except Exception as e:
        logging.error(f"❌ Error in process_message: {e}")
        return jsonify({"status": "error"}), 500