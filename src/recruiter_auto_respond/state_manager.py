import asyncio
import json
import logging
import os
from typing import Any, cast


class StateManager:
    """Manager for local state persistence."""

    def __init__(self, state_file: str) -> None:
        self.state_file = state_file

    async def load_state(self) -> dict[str, Any]:
        """Load state from file."""
        logging.info(f"Loading state from {self.state_file}")

        def _load() -> dict[str, Any]:
            if os.path.exists(self.state_file):
                with open(self.state_file, encoding="utf-8") as f:
                    data = json.load(f)
                    if not isinstance(data, dict):
                        logging.error(
                            "Invalid state file format in %s: "
                            "expected JSON object, got %s",
                            self.state_file,
                            type(data).__name__,
                        )
                        raise ValueError(
                            f"Invalid state file format: {self.state_file}"
                        )

                    return cast(dict[str, Any], data)
            # Default to a safe baseline if state doesn't exist
            return {"last_run_timestamp": "1970-01-01T00:00:00Z"}

        return await asyncio.to_thread(_load)

    async def save_state(self, state: dict[str, Any]) -> None:
        """Save state to file atomically."""
        logging.info(f"Saving state to {self.state_file}")
        tmp_state_file = self.state_file + ".tmp"

        def _save() -> None:
            try:
                with open(tmp_state_file, "w", encoding="utf-8") as f:
                    json.dump(state, f, indent=2)
                    f.flush()
                    os.fsync(f.fileno())
                os.replace(tmp_state_file, self.state_file)
            except Exception:
                logging.exception("Failed to save state")
                if os.path.exists(tmp_state_file):
                    os.remove(tmp_state_file)
                raise

        await asyncio.to_thread(_save)
