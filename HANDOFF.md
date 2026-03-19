# Handoff: Ticket 6 - State Management & Watermark Logic

## Overview
The next task is to implement the **Watermark** logic within `src/recruiter_auto_respond/state_manager.py`. This component is responsible for tracking progress reliably, ensuring no threads are skipped even if errors occur during processing.

## Current State
- `state_manager.py` already implements atomic JSON save/load.
- `last_run_timestamp` is currently initialized to 1970-01-01 in the stub.
- The "Watermark" logic—calculating the highest *consecutive* successful thread—is not yet implemented.

## Requirements (from Issue #7 & AGENTS.md)
1.  **Watermark Checkpointing:** Progress must be tracked by the date of the highest *consecutive* successful thread.
2.  **Success Definition:** For the purposes of advancing the watermark, a thread is considered successful once it has been **labeled in Gmail**. (Syncing to Sheets is handled in a subsequent step and doesn't block the watermark).
3.  **No Skipping (Hard Stop):** If a thread fails to be labeled (e.g., Gmail API error, LLM timeout), the watermark **cannot advance** past it, even if subsequent threads succeed. The pipeline should perform a hard stop at the first failure.
4.  **Atomic Persistence:** The `last_run_timestamp` must be updated in `state.json` only after the batch of consecutive threads is successfully labeled.
5.  **Sorting:** Threads must be processed from oldest to newest to ensure the watermark advances correctly.
6.  **Timestamp Format:** Use **ISO 8601 format** (e.g., `2026-03-18T12:00:00Z`) for `last_run_timestamp` in `state.json`.
7.  **Default Lookback:** If no `state.json` exists (initial run), default to a lookback period of **7 days**.

## Next Steps for New Agent
1.  **Orchestration Update:** Modify the pipeline orchestration (likely in `main.py`) to track the label status of each thread and pass this to the watermark logic.
2.  **Implementation:** Implement the watermark calculation logic in `StateManager`. Ensure it correctly identifies the timestamp of the last consecutive successful thread.
3.  **Unit Tests:** Create `tests/test_state_manager.py` (or update existing ones) to simulate:
    - A fully successful batch (watermark advances to the latest thread).
    - A batch with a failure in the middle (watermark stops at the thread immediately preceding the failure).
    - An initial run with no state file (verifying the 7-day lookback).
4.  **Validation:** Verify that `state.json` is updated atomically and only on success.
