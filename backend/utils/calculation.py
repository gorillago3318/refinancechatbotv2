import re
import logging

def extract_number(input_text):
    try:
        input_text = re.sub(r'[^\d.]', '', input_text)  # Remove non-digits except for the decimal
        if 'k' in input_text.lower():
            return float(input_text.replace('k', '')) * 1000
        return float(input_text.replace(',', ''))
    except ValueError as e:
        logging.error(f"Failed to extract number from input: {input_text} - Error: {e}")
        return None
