import logging
from flask import Flask, request, jsonify
from backend.helpers import update_lead_state, get_or_create_lead
from backend.calculations import calculate_refinance_savings

# Set up Flask app
app = Flask(__name__)

# Set up logging
logging.basicConfig(level=logging.INFO)

@app.route('/api/chatbot/webhook', methods=['POST'])
def whatsapp_webhook():
    """
    Webhook to handle incoming WhatsApp messages.
    """
    try:
        payload = request.get_json()
        logging.info(f"Incoming payload: {payload}")

        # Extract message safely
        try:
            messages = payload['entry'][0]['changes'][0]['value']['messages']
        except (KeyError, IndexError) as e:
            logging.error(f"Invalid payload structure: {payload}, Error: {str(e)}")
            return "Invalid payload structure: 'messages'", 400

        for message in messages:
            text = message.get('text', {}).get('body', '').strip()
            phone_number = message.get('from')

            if not phone_number:
                logging.error("Phone number not found in message.")
                return jsonify({'error': 'Phone number not found in the message.'}), 400

            response = handle_incoming_message(phone_number, text)
            return jsonify({'response': response})

    except Exception as e:
        logging.error(f"Error handling incoming message: {e}")
        return jsonify({'error': 'Internal server error'}), 500


def handle_incoming_message(phone_number, text):
    """
    Handle the incoming WhatsApp message and state transitions.
    """
    # Retrieve or create a lead
    lead = get_or_create_lead(phone_number)
    if not lead:
        logging.error("Could not retrieve or create a lead.")
        return "Error retrieving lead information. Please try again later."

    # Default state
    state = lead.state if lead and lead.state else 'start'
    logging.info(f"Incoming message from {phone_number}: {text} (state: {state})")

    # Handle user response based on current state
    response = handle_user_response(state, text, lead)
    return response


def handle_user_response(state, text, lead):
    """
    Handle user responses based on the current state.
    """
    try:
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
    except Exception as e:
        logging.error(f"Error handling user response for state {state}: {e}")
        return "An error occurred. Please try again later."
