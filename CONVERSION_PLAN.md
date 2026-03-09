# Design Plan: AI Recruiter Labeler & Syncer (Python Async)

This document outlines the architectural design for migrating `appscript.js` to a high-performance Python application using **Option B: Modern Async**, customized for local execution and `llama.cpp` integration.

## 1. Selected Architecture: Option B (Modern Async)
We will use Python's `asyncio` to manage high-concurrency I/O operations (Gmail API, LLM calls, and Sheets API).

### Key Stack
- **Runtime:** Python 3.10+
- **HTTP Client:** `httpx` OR `openai` (as an SDK for the local `llama.cpp` server).
- **LLM Provider:** `llama.cpp` server (OpenAI-compatible).
- **Gmail/Sheets API:** `google-api-python-client` with `asyncio` wrappers or `gspread-asyncio`.
- **Concurrency Control:** `asyncio.Semaphore(10)` to limit parallel LLM requests.

---

## 2. Component Design (User-Specified)

### A. Authentication & Secret Management
**Goal:** Simple, local configuration.
- **Implementation:** A `.env` file containing:
  - `LLM_API_URL`: (e.g., `http://localhost:8080/v1`)
  - `LLM_API_KEY`: (defaults to `sk-no-key-required` for local llama.cpp)
  - `GOOGLE_SHEET_ID`, `GMAIL_LABEL_NAME`.
  - `GOOGLE_APPLICATION_CREDENTIALS`: Path to `credentials.json`.
- **Google Auth:** Standard OAuth2 flow producing a local `token.json` for persistent sessions.

### B. State Management & "Late-Sync" Drift Protection
**Goal:** Track progress using a local JSON file while ensuring consistency with the Google Sheet.
- **Local State:** `state.json` stores `last_run_timestamp` (ISO format).
- **Late-Sync Strategy:** 
  1. The script processes and classifies all new emails found since `last_run_timestamp`.
  2. **Immediately before exporting** to the Google Sheet, the script fetches the entire 'Message ID' column from the Sheet.
  3. It filters the results one last time to remove any `message_id` already present in the Sheet.
  4. This ensures that even if the script is interrupted or the local state is out of sync, the Sheet remains the single source of truth for "already handled" messages.

### C. Gmail & LLM Pipeline
- **Search Query:** `-label:"{LABEL_NAME}" (category:primary OR category:updates) after:{TIMESTAMP}`.
  - *Note:* Removed `is:unread` to ensure all relevant emails are processed regardless of read status.
- **Classification (LLM Robustness):**
  - Use the `llama.cpp` `/v1/chat/completions` endpoint.
  - **JSON Mode:** Pass `response_format={"type": "json_object"}` to guarantee parsable output.
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

## 3. Brainstorming: Remaining Details & Edge Cases

### 1. llama.cpp Context Management
- **Detail:** Since `llama.cpp` is local, we should check the `n_ctx` (context window) of your loaded model. If an email exceeds this, we need to truncate the body gracefully to avoid API errors.

### 2. Sheet Initialization
- **Detail:** On the first run, the script should check if the "Emails" tab exists and create it with headers (`Thread ID`, `Message ID`, `Date`, etc.) if it is missing.

### 3. Rate Limiting (Local LLM)
- **Detail:** While `llama.cpp` doesn't have "API Quotas" like OpenAI, running 10 parallel requests (Semaphore) might saturate your CPU/GPU. We may need to adjust the `PARALLEL_LIMIT` based on your hardware's performance.

### 4. Logging & Verification
- **Detail:** Since we removed `is:unread`, the script might find the same threads in consecutive runs if the label hasn't been applied yet. The "Late-Sync" protection handles this, but the logs should clearly distinguish between "Classified Positive" and "Already in Sheet (Skipped)".

### 5. Content Sanitization
- **Detail:** Ensure we use a clean "Plain Text" extractor. Emails often contain messy signatures or legal disclaimers that consume tokens without helping classification.

**Next Step:** Once this design is confirmed, we can begin setting up the project structure and the `.env` / Auth configuration.
