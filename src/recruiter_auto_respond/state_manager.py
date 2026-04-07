import asyncio
import json
import logging
import os
from datetime import datetime, timedelta, timezone

from pydantic import BaseModel, Field


class AppState(BaseModel):
    """Schema for local application state."""

    last_run_timestamp: str = Field(default="1970-01-01T00:00:00Z")


class StateManager:
    """Manager for local state persistence using Pydantic."""

    def __init__(self, state_file: str, default_lookback_days: int = 7) -> None:
        self.state_file = state_file
        self.default_lookback_days = default_lookback_days

    def _get_default_timestamp(self) -> str:
        """Return default timestamp based on lookback days."""
        return (
            datetime.now(timezone.utc) - timedelta(days=self.default_lookback_days)
        ).strftime("%Y-%m-%dT%H:%M:%SZ")

    async def load_state(self) -> AppState:
        """Load state from file and return an AppState model."""
        logging.info(f"Loading state from {self.state_file}")

        def _load() -> AppState:
            if os.path.exists(self.state_file):
                try:
                    with open(self.state_file, encoding="utf-8") as f:
                        data = json.load(f)
                    return AppState.model_validate(data)
                except (json.JSONDecodeError, ValueError):
                    logging.exception(f"Failed to load or validate {self.state_file}")
                    # In case of corruption, return a default state
                    return AppState(last_run_timestamp=self._get_default_timestamp())

            return AppState(last_run_timestamp=self._get_default_timestamp())

        return await asyncio.to_thread(_load)

    async def save_state(self, state: AppState) -> None:
        """Save AppState to file atomically."""
        logging.info(f"Saving state to {self.state_file}")
        tmp_state_file = self.state_file + ".tmp"

        def _save() -> None:
            try:
                with open(tmp_state_file, "w", encoding="utf-8") as f:
                    f.write(state.model_dump_json(indent=2))
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
        app_state = await self.load_state()
        current_watermark = app_state.last_run_timestamp
        new_watermark = current_watermark

        for ts, success in results:
            if success:
                new_watermark = ts
            else:
                # Hard stop at the first failure
                break

        if new_watermark != current_watermark:
            app_state.last_run_timestamp = new_watermark
            await self.save_state(app_state)

        return new_watermark
