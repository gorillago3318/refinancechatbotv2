import os
from flask import Blueprint, request, jsonify
from backend.helpers import get_lead, update_lead_state, reset_lead_state
from backend.utils.whatsapp import send_whatsapp_message, send_message_to_admin
from backend.extensions import db
import json
import logging
import re
import openai
from backend.calculation import calculate_savings, format_years_saved
from backend.models import Lead

chatbot_bp = Blueprint('chatbot', __name__)
logger = logging.getLogger(__name__)

@chatbot_bp.route('/webhook', methods=['GET', 'POST'])
def whatsapp_webhook():
    if request.method == 'GET':
        return verify_webhook(request)
    elif request.method == 'POST':
        return handle_incoming_message(request)
    else:
        return jsonify({"error": "Method not allowed"}), 405

def verify_webhook(req):
    verify_token = os.getenv('WHATSAPP_VERIFY_TOKEN')
    mode = req.args.get('hub.mode')
    token = req.args.get('hub.verify_token')
    challenge = req.args.get('hub.challenge')
    logger.debug(f"Webhook verification: mode={mode}, token={token}, challenge={challenge}")

    if mode and token:
        if mode == 'subscribe' and token == verify_token:
            logger.info('WEBHOOK_VERIFIED')
            return challenge, 200
        else:
            logger.warning('WEBHOOK_VERIFICATION_FAILED: Token mismatch')
            return 'Verification token mismatch', 403
    return 'Hello World', 200

def handle_incoming_message(req):
    data = req.get_json()
    logger.debug(f"Received data: {json.dumps(data)}")

    try:
        entry = data['entry'][0]
        changes = entry['changes'][0]
        value = changes['value']
        messages = value.get('messages', [])

        if not messages:
            logger.info('No messages in this request.')
            return jsonify({"status": "no messages"}), 200

        message = messages[0]
        from_number = message['from']
        text = message.get('text', {}).get('body', '').strip()
        logger.info(f"Received message from {from_number}: {text}")
    except (KeyError, IndexError) as e:
        logger.error(f"Invalid payload structure: {e}")
        return jsonify({"error": "Invalid payload"}), 400

    # 'restart' command
    if text.lower() == 'restart':
        lead = get_lead(from_number)
        if lead:
            reset_lead_state(lead)
        else:
            lead = Lead(phone_number=from_number)
            db.session.add(lead)
            db.session.commit()

        restart_msg = (
            "Conversation restarted.\n\n"
            "Welcome to FinZo!\n\n"
            "I am FinZo, your AI Refinancing Assistant. I will guide you through the refinancing process and "
            "provide a detailed, accurate report based on your loan details.\n\n"
            "At any time, you may type 'restart' to start over.\n\n"
            "First, may I have your Name?"
        )
        send_whatsapp_message(from_number, restart_msg)
        update_lead_state(lead, 'get_name')
        return jsonify({"status": "conversation restarted"}), 200

    lead = get_lead(from_number)
    if not lead:
        lead = Lead(phone_number=from_number)
        db.session.add(lead)
        db.session.commit()
        greeting = (
            "Welcome to FinZo!\n\n"
            "I am FinZo, your AI Refinancing Assistant. I will help you understand your refinancing options and "
            "provide an accurate report based on your details.\n\n"
            "At any time, you may type 'restart' to start over.\n\n"
            "First, may I have your Name?"
        )
        send_whatsapp_message(from_number, greeting)
        update_lead_state(lead, 'get_name')
        return jsonify({"status": "greeting sent"}), 200

    state = lead.conversation_state

    if state == 'end':
        # After summary, user is asking questions.
        lead.question_count += 1
        db.session.commit()
        if lead.question_count > 5:
            contact_admin_prompt = (
                "It appears you have multiple questions. For further assistance, please contact our admin directly:\n\n"
                "https://wa.me/60167177813"
            )
            send_whatsapp_message(from_number, contact_admin_prompt)
            return jsonify({"status": "admin contact prompted"}), 200

        sanitized_question = sanitize_input(text)
        response = handle_user_question(sanitized_question)
        send_whatsapp_message(from_number, response)
        return jsonify({"status": "question answered"}), 200

    # Data collection states:
    if state == 'get_name':
        # Capitalize and title the name
        user_name = sanitize_input(text).title()
        lead.name = user_name
        db.session.commit()
        send_whatsapp_message(from_number, f"Nice to meet you, {lead.name}. Could you please provide your age? (18 to 70)")
        update_lead_state(lead, 'get_age')
        return jsonify({"status": "age prompt"})

    elif state == 'get_age':
        age = extract_number(text)
        if age is None or age < 18 or age > 70:
            send_whatsapp_message(from_number, "Please enter a valid age between 18 and 70.")
            return jsonify({"status": "invalid age"})
        lead.age = age
        db.session.commit()
        msg = (
            "Please provide the *Original Loan Amount*. This is the amount you borrowed from the bank.\n\n"
            "For example:\n"
            "300000\n"
            "300k\n"
            "RM300k\n\n"
            "Kindly enter the amount in one of the above formats."
        )
        send_whatsapp_message(from_number, msg)
        update_lead_state(lead, 'get_loan_amount')
        return jsonify({"status": "loan amount prompt"})

    elif state == 'get_loan_amount':
        loan_amount = parse_loan_amount(text)
        if loan_amount is None or loan_amount <= 0:
            send_whatsapp_message(from_number, "Please provide a valid loan amount, for example: 300000 or RM300k.")
            return jsonify({"status": "invalid loan amount"})
        lead.original_loan_amount = loan_amount
        db.session.commit()
        send_whatsapp_message(from_number, "How many years was the original loan tenure?\n\nFor example: 20 years, just type 20.")
        update_lead_state(lead, 'get_loan_tenure')
        return jsonify({"status": "loan tenure prompt"})

    elif state == 'get_loan_tenure':
        tenure = extract_number(text)
        if tenure is None or tenure <= 0:
            send_whatsapp_message(from_number, "Please provide a valid number of years. For example: 20.")
            return jsonify({"status": "invalid tenure"})
        lead.original_loan_tenure = tenure
        db.session.commit()
        send_whatsapp_message(from_number, "What is your current monthly repayment amount?\n\nFor example: RM2300.")
        update_lead_state(lead, 'get_current_repayment')
        return jsonify({"status": "current repayment prompt"})

    elif state == 'get_current_repayment':
        current_repayment = parse_loan_amount(text)
        if current_repayment is None or current_repayment <= 0:
            send_whatsapp_message(from_number, "Please provide a valid monthly repayment amount, for example: RM2500.")
            return jsonify({"status": "invalid current repayment"})
        lead.current_repayment = current_repayment
        db.session.commit()
        send_whatsapp_message(from_number, "Do you know your current interest rate?\n\nFor example: 4.5%. If you are not sure or cannot recall, type 'skip'.")
        update_lead_state(lead, 'get_interest_rate')
        return jsonify({"status": "interest rate prompt"})

    elif state == 'get_interest_rate':
        if text.lower() == 'skip':
            lead.interest_rate = None
            db.session.commit()
            send_whatsapp_message(from_number, "How many years remain on your loan?\n\nFor example: 15. If not sure, type 'skip'.")
            update_lead_state(lead, 'get_remaining_tenure')
            return jsonify({"status": "remaining tenure prompt"})
        else:
            rate = extract_number(text)
            if rate is None or rate <= 0:
                send_whatsapp_message(from_number, "Please provide a valid interest rate, for example: 4.5%. If not sure, type 'skip'.")
                return jsonify({"status": "invalid interest rate"})
            lead.interest_rate = rate
            db.session.commit()
            send_whatsapp_message(from_number, "How many years remain on your loan?\n\nFor example: 15. If not sure, type 'skip'.")
            update_lead_state(lead, 'get_remaining_tenure')
            return jsonify({"status": "remaining tenure prompt"})

    elif state == 'get_remaining_tenure':
        if text.lower() == 'skip':
            lead.remaining_tenure = lead.original_loan_tenure
            db.session.commit()
            perform_calculations_and_summary(from_number, lead)
            return jsonify({"status": "summary generated"})
        else:
            rem_tenure = extract_number(text)
            if rem_tenure is None or rem_tenure <= 0:
                send_whatsapp_message(from_number, "Please enter a valid number of years remaining, for example: 15.")
                return jsonify({"status": "invalid remaining tenure"})
            lead.remaining_tenure = rem_tenure
            db.session.commit()
            perform_calculations_and_summary(from_number, lead)
            return jsonify({"status": "summary generated"})

def perform_calculations_and_summary(from_number, lead):
    # Scenario with Bank A interest of 3.8%
    new_rate_annual = 3.8
    calculations = calculate_savings(
        loan_amount=lead.original_loan_amount,
        loan_tenure_years=lead.original_loan_tenure,
        current_repayment=lead.current_repayment,
        new_interest_rate_annual=new_rate_annual
    )

    lead.new_repayment = calculations['new_monthly_repayment']
    lead.monthly_savings = calculations['monthly_saving']
    lead.yearly_savings = calculations['annual_saving']
    lead.total_savings = calculations['total_saving']
    lead.years_saved = calculations['years_saved']
    db.session.commit()

    formatted_current = f"RM{lead.current_repayment:,.2f}"
    formatted_new = f"RM{calculations['new_monthly_repayment']:,.2f}"
    formatted_monthly = f"RM{calculations['monthly_saving']:,.2f}"
    formatted_annual = f"RM{calculations['annual_saving']:,.2f}"
    formatted_total = f"RM{calculations['total_saving']:,.2f}"
    formatted_years = format_years_saved(calculations['years_saved'])

    summary = (
        "This is your summary report:\n\n"
        f"- Current Repayment: *{formatted_current}*\n"
        f"- Estimated New Installment: *{formatted_new}*\n"
        f"- Monthly Savings: *{formatted_monthly}*\n"
        f"- Yearly Savings: *{formatted_annual}*\n"
        f"- Total Savings: *{formatted_total}*\n"
        f"- Years Saved: *{formatted_years}*\n\n"
    )

    if calculations['monthly_saving'] > 0:
        summary += (
            f"By refinancing at Bank A's 3.8% interest rate, you could potentially save *{formatted_total}* in total, "
            f"or reduce your loan tenure by *{formatted_years}*, assuming you continue the same monthly payment.\n\n"
            "A specialist will be assigned to provide a more detailed refinancing report.\n\n"
            "This service is free and has no obligations."
        )
    else:
        summary += (
            f"Congratulations, {lead.name}!\n\n"
            "It appears your current loan is already at a highly competitive rate, "
            "so refinancing may not offer immediate benefits."
        )

    send_whatsapp_message(from_number, summary)

    followup_msg = (
        "If you would like further assistance or want to explore more options, you can contact our admin directly:\n\n"
        "https://wa.me/60167177813\n\n"
        "If you have any questions about refinancing, feel free to ask now and I will do my best to assist you."
    )
    send_whatsapp_message(from_number, followup_msg)

    # Format the original loan amount for admin notification
    def formatted_original_loan_amount(amount):
        return f"RM{amount:,.2f}"

    # If interest_rate is None, it means user skipped
    interest_rate_info = lead.interest_rate if lead.interest_rate else "None"

    admin_notification = (
        "New Refinancing Lead:\n\n"
        f"Name: {lead.name}\n"
        f"Age: {lead.age}\n"
        f"Original Loan Amount: {formatted_original_loan_amount(lead.original_loan_amount)}\n"
        f"Original Tenure: {lead.original_loan_tenure} years\n"
        f"Remaining Tenure: {lead.remaining_tenure} years\n"
        f"Interest Rate (User Provided or Skipped): {interest_rate_info}\n"
        f"Current Monthly Repayment: {formatted_current}\n"
        f"New Monthly Repayment: {formatted_new}\n"
        f"Monthly Savings: {formatted_monthly}\n"
        f"Yearly Savings: {formatted_annual}\n"
        f"Total Savings: {formatted_total}\n"
        f"Years Saved: {formatted_years}\n"
        f"Contact Number: https://wa.me/{lead.phone_number}"
    )
    send_message_to_admin(admin_notification)

    update_lead_state(lead, 'end')
    lead.question_count = 0
    db.session.commit()

def formatted_original_loan_amount(amount):
    return f"RM{amount:,.2f}"

def handle_user_question(question):
    if not hasattr(handle_user_question, "faq"):
        try:
            with open(os.path.join(os.path.dirname(__file__), '..', 'data', 'faq.json'), 'r') as f:
                handle_user_question.faq = json.load(f)
        except FileNotFoundError:
            handle_user_question.faq = {}

    q = question.lower()
    if 'what is refinancing' in q or ('what' in q and 'refinance' in q):
        return handle_user_question.faq.get('what_is_refinancing', "I don't have that information at the moment.")
    elif 'how to refinance' in q or ('how' in q and 'refinance' in q):
        return handle_user_question.faq.get('how_to_refinance', "I don't have that information at the moment.")
    elif 'benefit of refinancing' in q or ('benefit' in q and 'refinancing' in q):
        return handle_user_question.faq.get('benefits_of_refinancing', "I don't have that information at the moment.")
    elif 'eligibility' in q:
        return handle_user_question.faq.get('eligibility_criteria', "I don't have that information at the moment.")
    elif 'process steps' in q or ('process' in q and 'step' in q):
        return handle_user_question.faq.get('process_steps', "I don't have that information at the moment.")
    else:
        return get_gpt35_response(question)

def get_gpt35_response(question):
    openai.api_key = os.getenv('OPENAI_API_KEY')
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": question}
            ],
            max_tokens=150,
            n=1,
            stop=None,
            temperature=0.7,
        )
        answer = response.choices[0].message['content'].strip()
        return answer
    except Exception as e:
        logger.error(f"Error with OpenAI API: {e}")
        return "I'm sorry, I couldn't process your request at the moment. Please try again later."

def sanitize_input(text):
    return re.sub(r'[^\w\s,.%-]', '', text)

def extract_number(text):
    match = re.search(r'\d+(\.\d+)?', text)
    if match:
        return float(match.group())
    return None

def parse_loan_amount(text):
    t = text.lower().replace('rm', '').replace(',', '').strip()
    multiplier = 1
    if 'k' in t:
        multiplier = 1000
        t = t.replace('k', '')
    try:
        return float(t) * multiplier
    except ValueError:
        return None
