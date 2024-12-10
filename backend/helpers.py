# backend/helpers.py

from backend.models import Lead  # ✅ Fixed import
from backend.extensions import db  # ✅ Fixed import


def get_lead(phone_number):
    """
    Retrieves the Lead instance based on the phone number.

    Parameters:
        phone_number (str): The WhatsApp number of the user.

    Returns:
        Lead or None: The Lead instance if found, else None.
    """
    return Lead.query.filter_by(phone_number=phone_number).first()


def update_lead_state(lead, new_state):
    """
    Updates the conversation state for a Lead.

    Parameters:
        lead (Lead): The Lead instance to update.
        new_state (str): The new conversation state.
    """
    if lead:
        lead.conversation_state = new_state
        db.session.commit()


def reset_lead_state(lead):
    """
    Resets the Lead's state and data to start a new conversation.

    Parameters:
        lead (Lead): The Lead instance to reset.
    """
    if lead:
        lead.name = None
        lead.age = None
        lead.original_loan_amount = None
        lead.original_loan_tenure = None
        lead.current_repayment = None
        lead.interest_rate = None
        lead.remaining_tenure = None
        lead.new_repayment = None
        lead.monthly_savings = None
        lead.yearly_savings = None
        lead.total_savings = None
        lead.years_saved = None
        lead.conversation_state = 'START'
        lead.question_count = 0
        lead.status = 'New'
        db.session.commit()
