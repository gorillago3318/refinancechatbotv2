import logging
from backend.extensions import db
from backend.models import Lead

def get_lead(phone_number):
    try:
        lead = Lead.query.filter_by(phone_number=phone_number).first()
        if not lead:
            logging.warning(f"No lead found for phone number {phone_number}")
        return lead
    except Exception as e:
        logging.error(f"Error getting lead for {phone_number}: {e}")
        return None

def update_lead_state(lead, new_state):
    try:
        lead.conversation_state = new_state
        db.session.commit()
        logging.info(f"Lead {lead.phone_number} state updated to '{new_state}'")
    except Exception as e:
        logging.error(f"Failed to update lead state for {lead.phone_number}: {e}")

def reset_lead_state(phone_number):
    try:
        lead = get_lead(phone_number)
        if lead:
            lead.conversation_state = None
            db.session.commit()
            logging.info(f"Lead {phone_number} state reset")
    except Exception as e:
        logging.error(f"Failed to reset lead state for {phone_number}: {e}")
