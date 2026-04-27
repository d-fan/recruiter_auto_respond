# Handoff: Improving Test Coverage & Testability

## Overview
The project is a high-performance Python migration of a Google Apps Script that automatically labels recruiter emails and syncs them to Google Sheets. The core functionality—including Gmail API interaction, LLM classification (via `llama.cpp`), Sheets syncing with drift protection, and state management—is now functional and orchestrated. 

The focus of this task is to **increase test coverage** and **improve code testability**, specifically through **unit tests**.

## Current State & Goals
- **Project Goal:** Ensure a reliable, long-term replacement for the original `appscript.js`.
- **Architecture:** 
  - `main.py`: Entry point and orchestrator.
  - `llm_client.py`: Classification logic with `tenacity` retries and `asyncio.Semaphore`.
  - `gmail_client.py`: Wrapper for Gmail API (Search, Fetch, Label).
  - `sheets_client.py`: Wrapper for Sheets API (ID fetching, Batch append).
  - `state_manager.py`: Atomic JSON checkpointing for the "Watermark" logic.
- **Existing Tests:**
  - **Unit Tests:** `test_gmail_client.py`, `test_llm_client.py`, `test_sheets_client.py`, `test_state_manager.py`, `test_main.py`.
  - **Conformance Tests:** `conformance_gmail.py`, `conformance_llm.py`, `conformance_sheets.py`.

## Task: Enhancing Testability & Coverage
The primary goal is to improve the **unit test suite**. There is no specific target coverage percentage, but the focus should be on high-risk areas and complex logic.

### Key Focus Areas:
1.  **Dependency Injection:** Review and refactor client initializations (Gmail, Sheets, LLM) to ensure all external dependencies can be cleanly mocked without relying on environment state or complex monkeypatching.
2.  **Refactoring for Testability:** Decouple `main.py` and the `process_messages` loop to allow for isolated unit testing of the orchestration and "Hard Stop" logic.
3.  **Edge Case Coverage:** Increase unit test coverage for rare failures:
    - Partial Sheets write failures.
    - Non-standard or malformed LLM JSON responses.
    - Gmail rate limit triggers (ensuring `tenacity` behaves as expected).
4.  **Property-Based Testing:** Consider using `Hypothesis` for the Watermark calculation logic in `state_manager.py` to ensure it handles all edge cases of thread ordering and success/failure status.

## Guidelines & Recommendations
- **Mocking Strategy:** There are no specific library preferences. If you recommend introducing a new mocking or testing library (beyond `unittest.mock` and `respx`), you must **justify the choice** and demonstrate the complexity/alternative of doing the same task without it.
- **CI/CD:** No CI pipeline is required for now, but ensure all tests can be run easily via `pytest`.

## Next Steps for New Agent
1.  **Baseline:** Run the existing test suite (`pytest`) and generate a coverage report (e.g., using `pytest-cov`) to identify the most significant "dark spots".
2.  **Prioritize:** Identify the 3-5 most critical areas for improvement based on logic complexity and failure risk.
3.  **Refactor & Propose:** Propose specific refactors to improve testability (e.g., introducing a `ServiceContainer` or standardizing constructor injection).
4.  **Implement:** Add new unit tests to cover the identified gaps and verify the refactors.
