import logging
from flask import request, jsonify
from backend.helpers import update_lead_state
from backend.calculations import calculate_refinance_savings

# Set up logging
logging.basicConfig(level=logging.INFO)

def whatsapp_webhook():
    """
    Webhook to handle incoming WhatsApp messages.
    """
    try:
        return handle_incoming_message(request)
    except Exception as e:
        logging.error(f"Error handling incoming message: {e}")
        return jsonify({'error': 'Internal server error'}), 500

def handle_incoming_message(request):
    """
    Handle the incoming WhatsApp message.
    """
    data = request.get_json()
    text = data.get('message', '').strip().lower()
    phone_number = data.get('phone_number')

    # Find or create lead based on phone_number
    lead = get_or_create_lead(phone_number)
    if not lead:
        return jsonify({'error': 'Could not retrieve lead information'}), 500

    # Default state
    state = lead.state if lead and lead.state else 'start'

    logging.info(f"Incoming message from {phone_number}: {text} (state: {state})")

    response = handle_user_response(state, text, lead)

    return jsonify({'response': response})

def handle_user_response(state, text, lead):
    """
    Handle user responses based on the current state.
    """
    if state == 'start':
        update_lead_state(lead, 'get_name')
        return "Welcome! What's your name?"

    elif state == 'get_name':
        lead.name = text.title()
        update_lead_state(lead, 'get_age')
        return f"Nice to meet you, {lead.name}! How old are you?"

    elif state == 'get_age':
        try:
            age = int(text)
            if age < 18 or age > 100:
                return "Please provide a valid age between 18 and 100."
            lead.age = age
            update_lead_state(lead, 'get_loan_amount')
            return "Great! What is your original loan amount?"
        except ValueError:
            return "Please provide a valid age as a number."

    elif state == 'get_loan_amount':
        try:
            loan_amount = float(text)
            lead.loan_amount = loan_amount
            update_lead_state(lead, 'get_optional_interest_rate')
            return "What's the interest rate for your current loan (optional)?"
        except ValueError:
            return "Please enter a valid loan amount."

    elif state == 'get_optional_interest_rate':
        try:
            interest_rate = float(text)
            lead.interest_rate = interest_rate
        except ValueError:
            logging.info("User skipped entering an interest rate.")

        update_lead_state(lead, 'get_optional_tenure')
        return "What is the remaining tenure for your current loan (optional)?"

    elif state == 'get_optional_tenure':
        try:
            tenure = int(text)
            lead.tenure = tenure
        except ValueError:
            logging.info("User skipped entering a tenure.")

        # Calculate refinance savings
        savings = calculate_refinance_savings(
            original_loan_amount=lead.loan_amount,
            original_tenure_years=lead.tenure if lead.tenure else 30,  # Default to 30 years
            current_monthly_repayment=1500,  # Example monthly repayment
            new_interest_rate=lead.interest_rate if lead.interest_rate else 3.5,  # Default to 3.5%
            new_tenure_years=30  # Default to 30 years
        )

        if savings:
            update_lead_state(lead, 'final_step')
            return (f"Here’s your refinance summary:\n"
                    f"New Monthly Repayment: RM{savings['new_monthly_repayment']}\n"
                    f"Monthly Savings: RM{savings['monthly_savings']}\n"
                    f"Yearly Savings: RM{savings['yearly_savings']}\n"
                    f"Lifetime Savings: RM{savings['lifetime_savings']}\n"
                    f"Years Saved: {savings['years_saved']} years\n"
                    f"To get a full report, please contact us.")
        else:
            update_lead_state(lead, 'error')
            return "An error occurred while calculating your refinance savings. Please try again later."

    else:
        logging.error(f"Invalid state: {state}")
        return "Invalid state. Please try again or type 'restart' to start over."
