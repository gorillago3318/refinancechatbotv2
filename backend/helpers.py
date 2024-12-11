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
    """Reset the state of the lead to start from the beginning."""
    lead = get_lead(from_number)
    if isinstance(lead, dict):  # If it's a dictionary
        lead['name'] = None
    elif hasattr(lead, 'name'):  # If it's an object
        lead.name = None
    else:
        logging.error(f"Lead is neither a dict nor an object: {lead}")
        
def update_lead_state(lead, new_state):
    """Update the state of a lead to a new state."""
    try:
        if isinstance(lead, dict):  # If it's a dictionary
            lead['state'] = new_state
        elif hasattr(lead, 'state'):  # If it's an object
            lead.state = new_state
        else:
            logging.error(f"Lead is neither a dict nor an object: {lead}")
        logging.info(f"Lead with phone_number {lead['phone_number']} updated to state '{new_state}'")
    except Exception as e:
        logging.error(f"Failed to update lead state for phone_number {lead['phone_number']}: {e}")