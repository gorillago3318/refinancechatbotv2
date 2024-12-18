import json
import os

def load_presets():
    """Load presets from the JSON file."""
    try:
        # Dynamically get the full path to the presets.json file
        presets_path = os.path.join(os.path.dirname(__file__), 'presets.json')
        with open(presets_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        raise Exception(f"❌ Error loading presets.json from {presets_path}: {e}")

# Load the presets globally
PRESETS = load_presets()
