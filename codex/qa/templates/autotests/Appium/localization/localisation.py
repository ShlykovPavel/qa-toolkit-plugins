import json
import os

def load_localization():
    with open(os.getenv('LOCALIZATION_FILE_PATH'), 'r') as f:
        localization = json.load(f)
    return localization