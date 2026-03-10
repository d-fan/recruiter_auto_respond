import logging
import json
import os

class StateManager:
    """Manager for local state persistence."""
    def __init__(self, state_file: str):
        self.state_file = state_file

    def load_state(self):
        """Load state from file."""
        logging.info(f"Loading state from {self.state_file}")
        if os.path.exists(self.state_file):
            with open(self.state_file, 'r') as f:
                return json.load(f)
        return {"last_run_timestamp": "2024-01-01T00:00:00Z"}

    def save_state(self, state: dict):
        """Save state to file."""
        logging.info(f"Saving state to {self.state_file}")
        with open(self.state_file, 'w') as f:
            json.dump(state, f, indent=2)
