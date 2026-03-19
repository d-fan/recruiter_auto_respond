import asyncio
import json
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any, cast

from recruiter_auto_respond.config import settings


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

            # Default to a 7-day lookback if state doesn't exist
            lookback_days = getattr(settings, "DEFAULT_LOOKBACK_DAYS", 7)
            default_timestamp = (
                datetime.now(timezone.utc) - timedelta(days=lookback_days)
            ).strftime("%Y-%m-%dT%H:%M:%SZ")
            return {"last_run_timestamp": default_timestamp}

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

    async def update_watermark(self, results: list[tuple[str, bool]]) -> str:
        """Update the watermark based on consecutive successful threads.

        Args:
            results: A list of (timestamp, success_flag) tuples,
                    sorted by timestamp.

        Returns:
            The new watermark timestamp.
        """
        state = await self.load_state()
        current_watermark = cast(str, state["last_run_timestamp"])
        new_watermark = current_watermark

        for ts, success in results:
            if success:
                new_watermark = ts
            else:
                # Hard stop at the first failure
                break

        if new_watermark != current_watermark:
            state["last_run_timestamp"] = new_watermark
            await self.save_state(state)

        return new_watermark
