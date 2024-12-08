# backend/utils/presets.py

import json
import os
import logging

logging.basicConfig(level=logging.DEBUG)

def load_presets():
    """
    Loads preset questions and answers from presets.json.
    """
    presets_path = os.path.join(os.path.dirname(__file__), 'presets.json')
    try:
        with open(presets_path, 'r') as file:
            presets = json.load(file)
            logging.info("Preset Q&A loaded successfully.")
            return presets
    except FileNotFoundError:
        logging.error(f"Preset file not found at path: {presets_path}")
        return []
    except json.JSONDecodeError as e:
        logging.error(f"Error decoding JSON from presets.json: {e}")
        return []
pass