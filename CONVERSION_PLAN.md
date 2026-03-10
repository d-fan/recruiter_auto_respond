# Design Plan: AI Recruiter Labeler & Syncer

This document outlines the architectural design for migrating `appscript.js` to a high-performance Python application using **Option B: Modern Async**, customized for local execution and `llama.cpp` integration.

## 1. Selected Architecture
We will use Python's `asyncio` to manage high-concurrency I/O operations (Gmail API, LLM calls, and Sheets API).

### Library Stack
- **Runtime:** Python 3.10+
- **HTTP Client:** `httpx`
  - *Justification:* Chosen over the `openai` SDK for its minimalist footprint and direct control over the request/response cycle. This is critical for debugging local `llama.cpp` integration where raw JSON logging is prioritized.
- **LLM Provider:** `llama.cpp` server (OpenAI-compatible).
- **Gmail/Sheets API:** `google-api-python-client` wrapped with `asyncio.to_thread`.
  - *Justification:* While heavier than community wrappers like `gspread`, it provides an official, unified interface for both Gmail and Sheets. This ensures long-term maintenance and robust support for batch operations needed for "Late-Sync" protection.
- **Authentication:** `google-auth-oauthlib` for the initial local OAuth2 flow.
- **Concurrency Control:** `asyncio.Semaphore(PARALLEL_LIMIT)` to limit parallel LLM requests.
- **Retries:** `tenacity` for robust error handling on all external API/LLM calls.

---

## 2. Component Design

### A. Authentication & Secret Management
**Goal:** Simple, local configuration.
- **Implementation:** A `.env` file containing:
  - `LLM_API_URL`: (e.g., `http://localhost:8080/v1`)
  - `LLM_API_KEY`: (defaults to `sk-no-key-required` for local llama.cpp)
  - `LLM_MAX_CONTEXT`: (e.g., `70000`) Maximum tokens/characters to send to the model.
  - `PARALLEL_LIMIT`: (e.g., `10`) Number of concurrent LLM requests.
  - `GOOGLE_SHEET_ID`, `GMAIL_LABEL_NAME`.
  - `GOOGLE_APPLICATION_CREDENTIALS`: Path to `credentials.json`.
- **Google Auth:** Standard OAuth2 flow producing a local `token.json` for persistent sessions.

### B. State Management & "Late-Sync" Drift Protection
**Goal:** Track progress using a local JSON file while ensuring consistency with the Google Sheet.
1. `state.json` stores `last_run_timestamp` (ISO format).
2. The script processes and classifies all new emails found since `last_run_timestamp`.
3. Immediately before exporting to the Google Sheet, the script fetches the entire 'Message ID' column from the Sheet.
4. It filters the results one last time to remove any `message_id` already present in the Sheet.
5. This ensures that even if the script is interrupted or the local state is out of sync, the Sheet remains the single source of truth for "already handled" messages.

### C. Gmail & LLM Pipeline
- **Search Query:** `-label:"{LABEL_NAME}" (category:primary OR category:updates) after:{TIMESTAMP}`.
- **Classification:**
  - Use the `llama.cpp` `/v1/chat/completions` endpoint.
  - **JSON Mode:** Pass `response_format={"type": "json_object"}` to guarantee parsable output.
  - **Context Handling:** Truncate email body to stay safely within `LLM_MAX_CONTEXT` (e.g., ~70k for current local model).
  - **Prompt:** Maintain the strict `{"isRecruiter": true/false}` JSON requirement.
- **Batch Action:** 
  1. Fetch message IDs from the Sheet.
  2. Apply labels to positive matches in Gmail (Batch).
  3. Append metadata to Google Sheets (Batch).

### D. Deployment (Local Crontab)
**Goal:** Automatic hourly execution on a local machine.
- **Setup:** A dedicated Python virtual environment (`.venv`).
- **Crontab Entry:**
  ```bash
  # Run every hour on the hour, logging output to a local file
  0 * * * * cd /path/to/project && ./.venv/bin/python main.py >> run.log 2>&1
  ```

---

## 3. Implementation Details & Assumptions

### 1. Sheet State
- **Assumption:** The Google Sheet is already set up with proper headers (`Thread ID`, `Message ID`, `Date`, etc.). Automatic initialization of an empty sheet is deferred for now.

### 2. Logging
- **Requirement:** Logs must clearly distinguish between a message being "Newly Classified" vs "Already in Sheet (Skipped)" during the late-sync phase.

### 3. Future Expansion: Content Sanitization
- **Vision:** While we will start with basic plain-text extraction, we will later implement a cleaner "Conversation Thread" extractor to support more complex LLM tasks like suggested replies and action items.

**Next Step:** Once this design is confirmed, we can begin setting up the project structure and the `.env` / Auth configuration.
