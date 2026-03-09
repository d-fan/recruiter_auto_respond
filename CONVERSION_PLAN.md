# Design Plan: AI Recruiter Labeler & Syncer

This document outlines the architectural design for migrating `appscript.js` to a high-performance Python application using **Option B: Modern Async**, customized for local execution and `llama.cpp` integration.

## 1. Selected Architecture
We will use Python's `asyncio` to manage high-concurrency I/O operations (Gmail API, LLM calls, and Sheets API).

### Key Stack
- **Runtime:** Python 3.10+
- **HTTP Client:** `httpx` OR `openai` (as an SDK for the local `llama.cpp` server).
- **LLM Provider:** `llama.cpp` server (OpenAI-compatible).
- **Gmail/Sheets API:** `google-api-python-client` with `asyncio` wrappers or `gspread-asyncio`.
- **Concurrency Control:** `asyncio.Semaphore(PARALLEL_LIMIT)` to limit parallel LLM requests.

---

## 2. Component Design

### A. Authentication & Secret Management
**Goal:** Simple, local configuration.
- **Implementation:** A `.env` file containing:
  - `LLM_API_URL`: (e.g., `http://localhost:8080/v1`)
  - `LLM_API_KEY`: (defaults to `sk-no-key-required` for local llama.cpp)
  - `LLM_MAX_CONTEXT`: (e.g., `70000`) Maximum **tokens** to send to the model (matches the model's context window size). The email body will be truncated by token count before being included in the prompt to stay within this limit.
  - `PARALLEL_LIMIT`: (e.g., `10`) Number of concurrent LLM requests.
  - `GOOGLE_SHEET_ID`, `GMAIL_LABEL_NAME`.
  - `GOOGLE_OAUTH_CLIENT_SECRET_FILE`: Path to OAuth client secrets JSON (downloaded from Google Cloud Console).
- **Google Auth:** Installed-app OAuth2 flow using `GOOGLE_OAUTH_CLIENT_SECRET_FILE` to generate and reuse a local `token.json` for persistent sessions.
- **Version Control Hygiene:** `.env`, `credentials.json`, and `token.json` must **never** be committed to version control. Add them to `.gitignore` so that secrets and refresh tokens remain local-only:
  ```gitignore
  .env
  credentials.json
  token.json
  ```

### B. State Management & "Late-Sync" Drift Protection
**Goal:** Track progress using a local JSON file while ensuring consistency with the Google Sheet.
1. `state.json` stores `last_run_timestamp` (ISO format) and optionally a lightweight index such as `last_synced_row` or a cache of recent `message_id`s.
2. The script processes and classifies all new emails found since `last_run_timestamp`.
3. Immediately before exporting to the Google Sheet, the script fetches only the **used range** of the 'Message ID' column, bounded to a recent window (e.g., from `last_synced_row` to the current last non-empty row, or the last N rows) instead of scanning the entire column on every run.
4. It filters the results one last time to remove any `message_id` already present in this bounded Sheet range and/or in the locally cached index.
5. This ensures drift protection (the Sheet remains the single source of truth for "already handled" messages) while avoiding an unbounded O(N) read on every run. A full reconciliation of the entire column can be performed as a rare maintenance step if needed.

### C. Gmail & LLM Pipeline
- **Search Query:** `-label:"{LABEL_NAME}" (category:primary OR category:updates) after:{TIMESTAMP}`.
- **Classification:**
  - Use the `llama.cpp` `/v1/chat/completions` endpoint.
  - **JSON Mode:** Pass `response_format={"type": "json_object"}` to guarantee parsable output.
  - **Context Handling:** Truncate email body by token count to stay safely within `LLM_MAX_CONTEXT` tokens (e.g., ~70k tokens for the current local model).
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
