# backend/helpers.py

from backend.models import Lead  # ✅ Fixed import
from backend.extensions import db  # ✅ Fixed import

def get_lead(from_number):
    """
    Retrieve a lead by phone number.
    """
    try:
        lead = Lead.query.filter_by(phone_number=from_number).first()
        if not lead:
            logging.warning(f"No lead found for phone_number: {from_number}")
        return lead
    except Exception as e:
        logging.error(f"Error retrieving lead for phone_number {from_number}: {e}")
        return None

def reset_lead_state(from_number):
    """
    Resets all the key attributes of the lead (name, age, loan amount, etc.) 
    and sets the conversation state back to 'get_name'.
    """
    lead = get_lead(from_number)
    if not lead:
        logging.warning(f"No lead found for phone_number {from_number}. Creating a new lead.")
        lead = Lead(phone_number=from_number)
        db.session.add(lead)
    
    lead.name = None
    lead.age = None
    lead.original_loan_amount = None
    lead.original_loan_tenure = None
    lead.current_repayment = None
    lead.conversation_state = 'get_name'  # Reset to initial state
    db.session.commit()

def update_lead_state(lead, new_state):
    """
    Update the lead's conversation state only.
    """
    if not lead:
        logging.warning(f"Lead not found or is None. Cannot update state to '{new_state}'")
        return {"status": "error", "message": "Lead not found"}
    
    if not new_state:
        logging.warning(f"New state is None or empty. Cannot update state.")
        return {"status": "error", "message": "New state is missing"}
    
    try:
        lead.conversation_state = new_state
        db.session.commit()
        logging.info(f"Lead with phone_number {lead.phone_number} updated to state '{new_state}'")
        return {"status": "success", "message": f"Lead state updated to '{new_state}'"}
    except Exception as e:
        logging.error(f"Failed to update lead state for phone_number {lead.phone_number}: {e}")
        db.session.rollback()
        return {"status": "error", "message": "Failed to update lead state"}
