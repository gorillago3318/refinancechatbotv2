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

openai.api_key = os.getenv("OPENAI_API_KEY").strip()

# Logging setup
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("debug.log")
    ]
)

ADMIN_PHONE_NUMBER = os.getenv('ADMIN_PHONE_NUMBER', '60126181683')
WHATSAPP_LINK = f"https://wa.me/{ADMIN_PHONE_NUMBER}"


PROMPTS = {
    'en': {
        'welcome_message': "🎉 Welcome to FinZo AI — Your Smart Refinancing Assistant! 🤖\n\n💸 Discover how much you can save by refinancing your home loan! Get quick insights and expert guidance to make the best decisions.\n\n🔄 Need to restart? Just type 'restart' anytime!",
        'choose_language': "🌐 Select Your Preferred Language:\n1️⃣ English \n2️⃣ Bahasa Malaysia \n3️⃣ 中文 (Chinese)",
        'get_name': "📝 *Step 1: Enter Your Name* \n\nPlease enter your *full name* for us to assist you better.\n\n💡 Example: John Doe",
        'get_loan_amount': "💸 *Step 2: Enter Your Loan Amount* \n\nEnter the *original loan amount* you borrowed.\n\n💡 Example: 250000",
        'get_loan_tenure': "📆 *Step 3: Enter Your Loan Tenure* \n\nHow many years was your *original loan tenure*?\n\n💡 Example: 30",
        'get_monthly_repayment': "💳 *Step 4: Enter Your Monthly Repayment* \n\nWhat’s your *current monthly repayment amount*?\n\n💡 Example: 2500",
        'thank_you': "🎉 Thank you! We've captured your details. We'll calculate your savings and send you a report shortly!"
    },
    'ms': {
        'welcome_message': "🎉 Selamat datang ke FinZo AI — Pembantu Pintar Pembiayaan Semula Anda! 🤖\n\n💸 Ketahui berapa banyak yang anda boleh jimatkan dengan pembiayaan semula pinjaman rumah anda! Dapatkan panduan pantas untuk membuat keputusan terbaik.\n\n🔄 Perlu mula semula? Taip 'restart' pada bila-bila masa!",
        'choose_language': "🌐 Pilih Bahasa Anda:\n1️⃣ English \n2️⃣ Bahasa Malaysia \n3️⃣ 中文 (Chinese)",
        'get_name': "📝 *Langkah 1: Masukkan Nama Anda* \n\nSila masukkan *nama penuh* anda untuk membolehkan kami membantu dengan lebih baik.\n\n💡 Contoh: Ali Bin Ahmad",
        'get_loan_amount': "💸 *Langkah 2: Masukkan Jumlah Pinjaman Anda* \n\nMasukkan *jumlah pinjaman asal* yang anda pinjam.\n\n💡 Contoh: 250000",
        'get_loan_tenure': "📆 *Langkah 3: Masukkan Tempoh Pinjaman Anda* \n\nBerapa tahun tempoh *pinjaman asal* anda?\n\n💡 Contoh: 30",
        'get_monthly_repayment': "💳 *Langkah 4: Masukkan Bayaran Bulanan Anda* \n\nApakah jumlah *bayaran bulanan semasa* anda?\n\n💡 Contoh: 2500",
        'thank_you': "🎉 Terima kasih! Kami telah merekodkan maklumat anda. Kami akan mengira penjimatan anda dan menghantar laporan tidak lama lagi!"
    },
    'zh': {
        'welcome_message': "🎉 欢迎使用 FinZo AI — 您的智能再融资助手! 🤖\n\n💸 快速了解通过再融资您的房屋贷款可以节省多少费用！获得专家指导，帮助您做出最佳决策。\n\n🔄 需要重新开始？随时输入 'restart'！",
        'choose_language': "🌐 请选择您的语言:\n1️⃣ English \n2️⃣ Bahasa Malaysia \n3️⃣ 中文 (Chinese)",
        'get_name': "📝 *步骤 1: 输入您的姓名* \n\n请提供您的*全名*，以便我们更好地帮助您。\n\n💡 示例: 王小明",
        'get_loan_amount': "💸 *步骤 2: 输入您的贷款金额* \n\n请输入您借款的*原始贷款金额*。\n\n💡 示例: 250000",
        'get_loan_tenure': "📆 *步骤 3: 输入您的贷款期限* \n\n您的*原始贷款期限*是多少年？\n\n💡 示例: 30",
        'get_monthly_repayment': "💳 *步骤 4: 输入您的每月还款金额* \n\n您的*当前每月还款金额*是多少？\n\n💡 示例: 2500",
        'thank_you': "🎉 谢谢！我们已记录您的详细信息。我们会计算您的节省金额，并尽快将报告发送给您！"
    }
}

openai.api_key = os.getenv("OPENAI_API_KEY").strip()

# Add greeting patterns
GREETING_PATTERNS = {
    'en': ['hi', 'hey', 'hello', 'start', 'begin', 'help'],
    'ms': ['hai', 'apa khabar', 'selamat', 'mula', 'tolong'],
    'zh': ['你好', '哈罗', '开始', '帮助']
}



# ✅ Add routes (Example Route)
@chatbot_bp.route('/test', methods=['GET'])
def test():
    return jsonify({"message": "Chatbot BP is working!"}), 200

def validate_language_choice(x, user_data=None):
    """ Validate that user input is 1, 2, or 3 for language selection. """
    if x not in ['1', '2', '3']:
        return False, "❌ Invalid choice. Please select 1 for English, 2 for Bahasa Malaysia, or 3 for Chinese."
    return True, ""

def validate_name(x, user_data=None):
    """ Validate that the name contains only letters and spaces. """
    if not x.replace(' ', '').isalpha():
        return False, "❌ Invalid name. Please enter letters only, without special characters or numbers."
    return True, ""

def validate_loan_amount(x, user_data=None):
    """ Validate that the loan amount is a positive numeric value. """
    if not x.isdigit() or int(x) <= 0:
        return False, "❌ Invalid amount. Please enter a valid loan amount (e.g., 250000)."
    return True, ""

def validate_loan_tenure(x, user_data=None):
    """ Validate that the loan tenure is a number between 1 and 40 years. """
    if not x.isdigit() or not (1 <= int(x) <= 40):
        return False, "❌ Invalid tenure. Please enter a value between 1 and 40 years."
    return True, ""

def validate_monthly_repayment(x, user_data=None):
    """ Validate that the monthly repayment is a positive numeric value. """
    if not x.isdigit() or int(x) <= 0:
        return False, "❌ Invalid repayment amount. Please enter a valid number greater than 0 (e.g., 2500)."
    return True, ""

def validate_process_completion(x, user_data=None):
    """ Always return True for process completion. """
    return True, ""

def is_greeting(message):
    """Check if the message is a greeting in any supported language."""
    message_lower = message.lower().strip()
    return any(
        greeting in message_lower 
        for greetings in GREETING_PATTERNS.values() 
        for greeting in greetings
    )


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

# Map numbers to language codes
LANGUAGE_MAP = {'1': 'en', '2': 'ms', '3': 'zh'}

LANGUAGE_OPTIONS = {
    'en': {
        'summary_title_1': "📊 Savings Summary Report",
        'summary_content_1': "✨ Here's what we’ve calculated for you:\n\n💳 Current Repayment: RM {current_repayment:.2f}\n📉 New Repayment: RM {new_repayment:.2f}\n💸 Monthly Savings: RM {monthly_savings:.2f}\n📆 Yearly Savings: RM {yearly_savings:.2f}\n💰 Lifetime Savings: RM {lifetime_savings:.2f}\n\n🎉 Great News! By refinancing, you could save up to {years_saved} year(s) and {months_saved} month(s) of repayments. Imagine the freedom of clearing your loan faster or having extra cash every month!",
        'summary_title_2': "🛠️ What's Next? Your Path to Savings",
        'summary_content_2': f"You now have 3 powerful options to achieve your financial goals:\n\n1️⃣ Lower Your Monthly Repayment – Enjoy immediate savings and extra cash flow.\n2️⃣ Shorten Your Loan Tenure – Achieve financial freedom faster and save on total interest paid.\n3️⃣ Cash Out Home Equity – Unlock funds for renovations, investments, or other financial needs.\n\n🌟 Our Specialist Will Assist You! A refinance expert will reach out to you shortly to discuss your options and ensure you make the best decision.\n\n📞 Need urgent assistance? Contact us directly at https://wa.me/60126181683.",
        'summary_title_3': "Inquiry Mode Activated",
        'summary_content_3': f"You're now talking to Finzo AI.\n\nJust ask any questions in regards to refinancing and home loans. I will try my best to assist you.\n\nSince I am still a language model, I might not be able to answer some of your questions. Not to worry, you can always drop a message to our admin at https://wa.me/60126181683 if you need further assistance."
    },
    'ms': {
        'summary_title_1': "📊 Laporan Ringkasan Penjimatan",
        'summary_content_1': "✨ Berikut adalah hasil pengiraan kami:\n\n💳 Bayaran Bulanan Semasa: RM {current_repayment:.2f}\n📉 Bayaran Bulanan Baru: RM {new_repayment:.2f}\n💸 Penjimatan Bulanan: RM {monthly_savings:.2f}\n📆 Penjimatan Tahunan: RM {yearly_savings:.2f}\n💰 Penjimatan Sepanjang Tempoh: RM {lifetime_savings:.2f}\n\n🎉 Berita Baik! Dengan pembiayaan semula, anda boleh menjimatkan sehingga {years_saved} tahun dan {months_saved} bulan pembayaran!",
        'summary_title_2': "🛠️ Apa Langkah Seterusnya?",
        'summary_content_2': f"Anda kini mempunyai 3 pilihan hebat untuk mencapai matlamat kewangan anda:\n\n1️⃣ Kurangkan Bayaran Bulanan – Nikmati penjimatan segera dan aliran tunai tambahan.\n2️⃣ Pendekkan Tempoh Pinjaman – Capai kebebasan kewangan lebih cepat dan jimat faedah keseluruhan.\n3️⃣ Tunaikan Ekuiti Rumah – Dapatkan dana untuk pengubahsuaian, pelaburan, atau keperluan lain.\n\n🌟 Pakar Kami Akan Membantu Anda! Pakar pembiayaan semula akan menghubungi anda untuk membincangkan pilihan dan membantu anda membuat keputusan terbaik.\n\n📞 Perlukan bantuan segera? Hubungi kami di https://wa.me/60126181683.",
        'summary_title_3': "Mod Pertanyaan Diaktifkan",
        'summary_content_3': f"Anda kini berhubung dengan Finzo AI.\n\nTanya sebarang soalan mengenai pembiayaan semula dan pinjaman rumah. Saya akan cuba sedaya upaya untuk membantu anda.\n\nOleh kerana saya masih model bahasa, mungkin saya tidak dapat menjawab semua soalan anda. Jangan risau, anda boleh hubungi admin kami di https://wa.me/60126181683 untuk bantuan lanjut."
    },
    'zh': {
        'summary_title_1': "📊 储蓄总结报告",
        'summary_content_1': "✨ 这是我们为您计算的结果:\n\n💳 当前还款金额: RM {current_repayment:.2f}\n📉 新还款金额: RM {new_repayment:.2f}\n💸 每月节省: RM {monthly_savings:.2f}\n📆 每年节省: RM {yearly_savings:.2f}\n💰 总节省: RM {lifetime_savings:.2f}\n\n🎉 好消息！通过再融资，您最多可节省 {years_saved} 年和 {months_saved} 个月的还款！",
        'summary_title_2': "🛠️ 接下来的步骤?",
        'summary_content_2': f"您现在有 3 个强大的选项来实现您的财务目标:\n\n1️⃣ 降低月供 – 享受即时节省和现金流改善。\n2️⃣ 缩短贷款期限 – 更快实现财务自由并减少总利息。\n3️⃣ 提取房屋净值 – 获取资金用于装修、投资或其他财务需求。\n\n🌟 我们的专家将帮助您！再融资专家将尽快与您联系，帮助您做出最佳决策。\n\n📞 需要紧急帮助？请直接联系我们 https://wa.me/60126181683。",
        'summary_title_3': "查询模式已激活",
        'summary_content_3': f"您现在正在与 Finzo AI 对话。\n\n请随时提问有关再融资和房屋贷款的问题，我会尽力协助您。\n\n由于我仍然是一个语言模型，我可能无法回答所有问题。如果需要进一步帮助，请随时联系我们的管理员 https://wa.me/60126181683。"
    }
}

def get_message(key, language_code):
    """ Retrieve a message from the appropriate language file. """
    try:
        # Map language codes if provided as 1, 2, or 3
        if language_code in ['1', '2', '3']:
            language_code = {'1': 'en', '2': 'ms', '3': 'zh'}[language_code]

        # Check LANGUAGE_OPTIONS first, then fallback to PROMPTS
        if language_code in LANGUAGE_OPTIONS and key in LANGUAGE_OPTIONS[language_code]:
            message = LANGUAGE_OPTIONS[language_code].get(key, 'Message not found')
        elif language_code in PROMPTS and key in PROMPTS[language_code]:
            message = PROMPTS[language_code].get(key, 'Message not found')
        else:
            logging.error(f"Key '{key}' not found in LANGUAGE_OPTIONS or PROMPTS for language '{language_code}'.")
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
        message_body = data['entry'][0]['changes'][0]['value']['messages'][0]['text']['body'].strip()

        logging.info(f"💎 Incoming message from {phone_number}: {message_body}")

        # Get ChatflowTemp Data
        user_data = db.session.query(ChatflowTemp).filter_by(phone_number=phone_number).first()

        # Handle greetings or new user
        if not user_data or is_greeting(message_body):
            if user_data:
                # Reset existing user if greeting received
                user_data.current_step = 'choose_language'
                user_data.mode = 'flow'
                user_data.name = None
                user_data.original_loan_amount = None
                user_data.original_loan_tenure = None
                user_data.current_repayment = None
            else:
                # Create new user
                user_data = ChatflowTemp(
                    phone_number=phone_number,
                    current_step='choose_language',
                    language_code='en',
                    mode='flow'
                )
                db.session.add(user_data)
            
            db.session.commit()
            message = PROMPTS['en']['welcome_message'] + "\n\n" + PROMPTS['en']['choose_language']
            send_whatsapp_message(phone_number, message)
            return jsonify({"status": "success"}), 200

        # Handle 24-hour reminder with timezone fix
        last_active = user_data.updated_at.replace(tzinfo=MYT)
        if (datetime.now(MYT) - last_active).total_seconds() > 86400:  # 24 hours
            reminder_message = (
                "Welcome back! If you'd like to recalculate your savings, please type 'restart'. "
                "Otherwise, feel free to ask any questions about refinancing or home loans!"
            )
            send_whatsapp_message(phone_number, reminder_message)

        # Rest of the existing process_message code remains the same...
        # Handle "restart" command
        if message_body.lower() == 'restart':
            logging.info(f"🔄 Restarting flow for user {phone_number}")
            user_data.current_step = 'choose_language'
            user_data.mode = 'flow'
            user_data.name = None
            user_data.original_loan_amount = None
            user_data.original_loan_tenure = None
            user_data.current_repayment = None
            db.session.commit()
            message = PROMPTS['en']['welcome_message'] + "\n\n" + PROMPTS['en']['choose_language']
            send_whatsapp_message(phone_number, message)
            return jsonify({"status": "success"}), 200

        # Check if user is in query mode
        if user_data.mode == 'query':
            logging.info(f"🟢 User {phone_number} is in query mode.")
            response = handle_gpt_query(message_body, user_data, phone_number)
            send_whatsapp_message(phone_number, response)
            return jsonify({"status": "success"}), 200

        # Process Current Step
        current_step = user_data.current_step or 'choose_language'
        step_info = STEP_CONFIG.get(current_step)
        
        is_valid, error_message = step_info['validator'](message_body, user_data)
        if not is_valid:
            send_whatsapp_message(phone_number, error_message)
            return jsonify({"status": "failed"}), 400

        process_user_input(current_step, user_data, message_body)

        if step_info['next_step'] == 'process_completion':
            return handle_process_completion(phone_number)

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

        # Hardcoded admin phone number
        admin_phone_number = '60126181683'

        # Calculate refinance savings
        calculation_results = calculate_refinance_savings(
            user_data.original_loan_amount, 
            user_data.original_loan_tenure, 
            user_data.current_repayment
        )

        # Handle case where new repayment is higher than current repayment
        if calculation_results.get('new_monthly_repayment', 0.0) >= user_data.current_repayment:
            message = (
                "Thank you for using FinZo AI! Based on our calculations, refinancing may result in higher payments.\n\n"
                "💬 If you'd still like to explore options, feel free to contact our admin for further assistance at "
                f"https://wa.me/{admin_phone_number}"
            )
            send_whatsapp_message(phone_number, message)
            user_data.mode = 'query'
            db.session.commit()
            return jsonify({"status": "success"}), 200

        # Handle no results or no savings
        if not calculation_results or calculation_results.get('monthly_savings', 0) <= 0:
            message = (
                "Thank you for using FinZo AI! Your current loan rates are already in great shape. "
                "We’ll be in touch if better offers become available.\n\n"
                f"📞 Contact admin at https://wa.me/{admin_phone_number} for help or questions!"
            )
            send_whatsapp_message(phone_number, message)
            user_data.mode = 'query'
            db.session.commit()
            return jsonify({"status": "success"}), 200

        # Prepare and send summary messages
        language_code = user_data.language_code if user_data.language_code in LANGUAGE_OPTIONS else 'en'
        try:
            summary_messages = prepare_summary_messages(user_data, calculation_results, language_code)
            for message in summary_messages:
                send_whatsapp_message(phone_number, message)
        except Exception as e:
            logging.error(f"❌ Error while preparing or sending summary messages: {str(e)}")
            return jsonify({"status": "error", "message": "Failed to send summary messages."}), 500

        # Notify admin and update database
        try:
            send_new_lead_to_admin(phone_number, user_data, calculation_results)
            update_database(phone_number, user_data, calculation_results)
        except Exception as e:
            logging.error(f"❌ Error while notifying admin or updating database: {str(e)}")
            return jsonify({"status": "error", "message": "Failed to update admin or database."}), 500

        # Commit only after all tasks succeed
        user_data.mode = 'query'
        db.session.commit()

        return jsonify({"status": "success"}), 200

    except Exception as e:
        logging.error(f"❌ Error in handle_process_completion: {str(e)}")
        logging.error(f"Traceback: {traceback.format_exc()}")
        db.session.rollback()
        return jsonify({"status": "error", "message": "Something went wrong"}), 500

def prepare_summary_messages(user_data, calculation_results, language_code):
    """ Prepares the summary messages to be sent to the user. """
    
    # Summary 1 - Savings Report
    summary_message_1 = f"{get_message('summary_title_1', language_code)}\n\n" + get_message('summary_content_1', language_code).format(
        current_repayment=getattr(user_data, 'current_repayment', 0.0),  # Fixed
        new_repayment=calculation_results.get('new_monthly_repayment', 0.0),
        monthly_savings=calculation_results.get('monthly_savings', 0.0),
        yearly_savings=calculation_results.get('yearly_savings', 0.0),
        lifetime_savings=calculation_results.get('lifetime_savings', 0.0),
        years_saved=calculation_results.get('years_saved', 0),  # Default to 0
        months_saved=calculation_results.get('months_saved', 0) # Default to 0
    )

    # Summary 2 - What's Next
    summary_message_2 = f"{get_message('summary_title_2', language_code)}\n\n" + get_message('summary_content_2', language_code).format(
        monthly_savings=calculation_results.get('monthly_savings', 0.0),
        yearly_savings=calculation_results.get('yearly_savings', 0.0),
        lifetime_savings=calculation_results.get('lifetime_savings', 0.0),
        years_saved=calculation_results.get('years_saved', 0),
        months_saved=calculation_results.get('months_saved', 0)
    )

    # Hardcoded admin phone number
    admin_phone_number = '60126181683'
    whatsapp_link = f"https://wa.me/{admin_phone_number}"

    summary_title_3 = get_message('summary_title_3', language_code)
    summary_content_3 = get_message('summary_content_3', language_code).format(
        whatsapp_link=whatsapp_link
    )
    summary_message_3 = f"{summary_title_3}\n\n{summary_content_3}"

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
    """Enhanced admin notification with clearer formatting."""
    admin_number = os.getenv('ADMIN_PHONE_NUMBER')
    if not admin_number:
        logging.error("ADMIN_PHONE_NUMBER not set in environment variables.")
        return
    
    message = (
        f"🔔 *NEW LEAD DETAILS*\n\n"
        f"👤 *Client Information*\n"
        f"• Name: {getattr(user_data, 'name', 'Unknown')}\n"
        f"• Contact: wa.me/{phone_number}\n\n"
        f"💰 *Loan Details*\n"
        f"• Current Amount: RM {getattr(user_data, 'original_loan_amount', 'N/A'):,.2f}\n"
        f"• Current Tenure: {getattr(user_data, 'original_loan_tenure', 'N/A')} years\n"
        f"• Current Monthly: RM {getattr(user_data, 'current_repayment', 'N/A'):,.2f}\n\n"
        f"📊 *Potential Savings*\n"
        f"• New Monthly: RM {calculation_results.get('new_monthly_repayment', 0):,.2f}\n"
        f"• Monthly Savings: RM {calculation_results.get('monthly_savings', 0):,.2f}\n"
        f"• Yearly Savings: RM {calculation_results.get('yearly_savings', 0):,.2f}\n"
        f"• Total Savings: RM {calculation_results.get('lifetime_savings', 0):,.2f}\n"
        f"• Time Saved: {calculation_results.get('years_saved', 0)} years"
    )

    send_whatsapp_message(admin_number, message)

def handle_gpt_query(question, user_data, phone_number):
    """Handles GPT query requests with improved response handling."""
    try:
        # Enhanced system prompt with specific instruction for direct answers
        system_prompt = (
            "You are a helpful assistant focused on refinance and home loan topics. Important guidelines:\n"
            "1. Give direct, specific answers to questions\n"
            "2. For admin contact questions, provide this number: wa.me/60126181683\n"
            "3. Identify yourself as FinZo AI when asked about identity\n"
            "4. Keep responses concise and focused\n"
            "5. Don't repeat generic offers of help unless specifically relevant\n"
            "6. For name questions, say: 'I am FinZo AI, your refinancing assistant.'\n"
            "7. For employer questions, say: 'I am FinZo AI, created to help with refinancing and home loan queries.'\n"
            "8. Maintain focus on refinancing, home loans, mortgage rates, eligibility, payments, and savings"
        )

        # Handle common questions directly without GPT
        lower_question = question.lower()
        if "admin" in lower_question or "contact" in lower_question:
            return "You can contact our admin directly at wa.me/60126181683"
        elif "your name" in lower_question:
            return "I am FinZo AI, your refinancing assistant."
        elif "who" in lower_question and "work" in lower_question:
            return "I am FinZo AI, created to help with refinancing and home loan queries."

        # For other questions, use GPT-3.5-turbo
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": question}
            ],
            temperature=0.7,
            max_tokens=150
        )
        
        message = response.choices[0].message.content.strip()
        
        # Log query
        log_gpt_query(phone_number, question, message)
        
        return message

    except Exception as e:
        logging.error(f"❌ Error while handling GPT query for {phone_number}: {str(e)}")
        return (
            "We're currently experiencing issues processing your request. "
            "Please try again later or contact our admin for assistance: wa.me/60126181683"
        )


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
