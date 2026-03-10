import logging
import json
import os

class StateManager:
    """Manager for local state persistence."""
    def __init__(self, state_file: str) -> None:
        self.state_file = state_file

    def load_state(self) -> dict:
        """Load state from file."""
        logging.info(f"Loading state from {self.state_file}")
        if os.path.exists(self.state_file):
            with open(self.state_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        # Default to a safe baseline if state doesn't exist
        return {"last_run_timestamp": "1970-01-01T00:00:00Z"}

    def save_state(self, state: dict) -> None:
        """Save state to file atomically."""
        logging.info(f"Saving state to {self.state_file}")
        tmp_state_file = self.state_file + ".tmp"
        try:
            with open(tmp_state_file, 'w', encoding='utf-8') as f:
                json.dump(state, f, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_state_file, self.state_file)
        except Exception as e:
            logging.error(f"Failed to save state: {e}")
            if os.path.exists(tmp_state_file):
                os.remove(tmp_state_file)
            raise
