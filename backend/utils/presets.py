import json
import os
import logging

# Configure logging for this module
logging.basicConfig(level=logging.DEBUG)

def load_presets():
    """
    Loads preset questions and answers from presets.json.
    
    Returns:
        list: A list of questions and answers from the presets file.
    """
    # Get the absolute path of the presets.json file
    presets_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'presets.json')
    
    try:
        with open(presets_path, 'r', encoding='utf-8') as file:
            presets = json.load(file)
            logging.info(f"✅ Preset Q&A loaded successfully from {presets_path}. Total presets: {len(presets)}")
            return presets
    except FileNotFoundError:
        logging.error(f"❌ Preset file not found at path: {presets_path}. Make sure the file exists.")
        return []  # Return an empty list to avoid breaking the program
    except json.JSONDecodeError as e:
        logging.error(f"❌ Error decoding JSON from presets.json at path: {presets_path}. Error: {e}")
        return []  # Return an empty list if JSON is malformed
    except Exception as e:
        logging.error(f"❌ Unexpected error while loading presets.json: {e}")
        return []  # Catch-all for any other unforeseen errors
