import json
import os
import tempfile
from collections.abc import Generator
from datetime import datetime, timedelta, timezone

import pytest

from recruiter_auto_respond.config import settings
from recruiter_auto_respond.state_manager import StateManager


@pytest.fixture
def temp_state_file() -> Generator[str, None, None]:
    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        tmp_name = tmp.name
    yield tmp_name
    if os.path.exists(tmp_name):
        os.remove(tmp_name)


@pytest.mark.asyncio
async def test_load_state_no_file(temp_state_file: str) -> None:
    if os.path.exists(temp_state_file):
        os.remove(temp_state_file)

    manager = StateManager(temp_state_file)
    state = await manager.load_state()

    # Check if the timestamp is roughly DEFAULT_LOOKBACK_DAYS ago
    last_run = state.get("last_run_timestamp")
    assert last_run is not None

    dt = datetime.fromisoformat(last_run.replace("Z", "+00:00"))
    now = datetime.now(timezone.utc)
    expected = now - timedelta(days=settings.DEFAULT_LOOKBACK_DAYS)

    # Allow for some small difference in time
    time_threshold_seconds = 60
    assert abs((dt - expected).total_seconds()) < time_threshold_seconds


@pytest.mark.asyncio
async def test_load_state_existing_file(temp_state_file: str) -> None:
    timestamp = "2026-03-18T12:00:00Z"
    with open(temp_state_file, "w") as f:
        json.dump({"last_run_timestamp": timestamp}, f)

    manager = StateManager(temp_state_file)
    state = await manager.load_state()
    assert state["last_run_timestamp"] == timestamp


@pytest.mark.asyncio
async def test_save_state(temp_state_file: str) -> None:
    manager = StateManager(temp_state_file)
    timestamp = "2026-03-18T13:00:00Z"
    await manager.save_state({"last_run_timestamp": timestamp})

    with open(temp_state_file) as f:
        data = json.load(f)
    assert data["last_run_timestamp"] == timestamp


@pytest.mark.asyncio
async def test_update_watermark_all_success(temp_state_file: str) -> None:
    manager = StateManager(temp_state_file)
    # Initial state
    initial_ts = "2026-03-18T10:00:00Z"
    await manager.save_state({"last_run_timestamp": initial_ts})

    # Results: (timestamp, success)
    results = [
        ("2026-03-18T11:00:00Z", True),
        ("2026-03-18T12:00:00Z", True),
        ("2026-03-18T13:00:00Z", True),
    ]

    new_ts = await manager.update_watermark(results)
    assert new_ts == "2026-03-18T13:00:00Z"

    state = await manager.load_state()
    assert state["last_run_timestamp"] == "2026-03-18T13:00:00Z"


@pytest.mark.asyncio
async def test_update_watermark_with_failure(temp_state_file: str) -> None:
    manager = StateManager(temp_state_file)
    # Initial state
    initial_ts = "2026-03-18T10:00:00Z"
    await manager.save_state({"last_run_timestamp": initial_ts})

    # Results: (timestamp, success)
    results = [
        ("2026-03-18T11:00:00Z", True),
        ("2026-03-18T12:00:00Z", False),  # Failure
        ("2026-03-18T13:00:00Z", True),  # Success after failure (should not count)
    ]

    new_ts = await manager.update_watermark(results)
    assert new_ts == "2026-03-18T11:00:00Z"

    state = await manager.load_state()
    assert state["last_run_timestamp"] == "2026-03-18T11:00:00Z"


@pytest.mark.asyncio
async def test_update_watermark_first_failure(temp_state_file: str) -> None:
    manager = StateManager(temp_state_file)
    # Initial state
    initial_ts = "2026-03-18T10:00:00Z"
    await manager.save_state({"last_run_timestamp": initial_ts})

    # Results: (timestamp, success)
    results = [
        ("2026-03-18T11:00:00Z", False),  # First one fails
        ("2026-03-18T12:00:00Z", True),
    ]

    new_ts = await manager.update_watermark(results)
    assert new_ts == initial_ts  # Should stay at initial

    state = await manager.load_state()
    assert state["last_run_timestamp"] == initial_ts


@pytest.mark.asyncio
async def test_update_watermark_no_results(temp_state_file: str) -> None:
    manager = StateManager(temp_state_file)
    initial_ts = "2026-03-18T10:00:00Z"
    await manager.save_state({"last_run_timestamp": initial_ts})

    new_ts = await manager.update_watermark([])
    assert new_ts == initial_ts

    state = await manager.load_state()
    assert state["last_run_timestamp"] == initial_ts
