import json
import os

STATE_FILE = "state.json"

def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    return {"seen_matches": [], "pausado": False}

def save_state(seen_matches, pausado):
    with open(STATE_FILE, "w") as f:
        json.dump({
            "seen_matches": list(seen_matches),
            "pausado": pausado
        }, f)
