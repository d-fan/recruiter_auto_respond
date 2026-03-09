# Design Plan: AI Recruiter Labeler & Syncer (Python Async)

This document outlines the architectural design for migrating `appscript.js` to a high-performance Python application using **Option B: Modern Async**, customized for local execution.

## 1. Selected Architecture: Option B (Modern Async)
We will use Python's `asyncio` to manage high-concurrency I/O operations (Gmail API, LLM calls, and Sheets API).

### Key Stack
- **Runtime:** Python 3.10+
- **HTTP Client:** `httpx` (Asynchronous HTTP requests)
- **Gmail/Sheets API:** `google-api-python-client` with `asyncio` wrappers or `gspread-asyncio`.
- **Concurrency Control:** `asyncio.Semaphore(10)` to limit parallel LLM requests.

---

## 2. Component Design (User-Specified)

### A. Authentication & Secret Management
**Goal:** Simple, local configuration.
- **Implementation:** A `.env` file containing:
  - `LLM_API_KEY`, `LLM_USER`, `LLM_PASS`, `LLM_API_URL`.
  - `GOOGLE_SHEET_ID`, `GMAIL_LABEL_NAME`.
  - `GOOGLE_APPLICATION_CREDENTIALS` (path to `credentials.json`).
- **Google Auth:** Standard OAuth2 flow producing a local `token.json` for persistent sessions.

### B. State Management & Drift Protection
**Goal:** Track progress using a local JSON file while ensuring consistency with the Google Sheet.
- **Local State:** `state.json` will store:
  - `last_run_timestamp`: The ISO timestamp of the last successful scan.
- **Drift Protection Strategy (Sync-before-Write):**
  1. At the start of a sync run, the script will **fetch the entire 'Message ID' column** from the Google Sheet.
  2. This list will be used as the "Source of Truth" to filter out emails that have already been recorded.
  3. This prevents duplicates even if `state.json` is deleted or the script is moved to a different machine.

### C. Gmail & LLM Pipeline
- **Search:** `is:unread -label:"{LABEL_NAME}"` (similar to original).
- **Classification:** Async workers fetch thread content -> LLM classification -> Collect results.
- **Batch Action:** Only after all classifications are done:
  1. Apply labels to all positive matches in one `batchModify` call.
  2. Append all new entries to the Google Sheet in one `append_rows` call.

### D. Deployment (Local Crontab)
**Goal:** Automatic execution on a local machine (e.g., Linux/macOS).
- **Setup:** A dedicated Python virtual environment (`.venv`).
- **Crontab Entry:**
  ```bash
  # Run every 30 minutes, logging output to a local file
  */30 * * * * cd /path/to/project && ./.venv/bin/python main.py >> run.log 2>&1
  ```

---

## 3. Brainstorming: Remaining Details & Edge Cases

Before implementation, we should refine these aspects:

### 1. LLM Robustness
- **Response Parsing:** What if the LLM returns Markdown blocks (e.g., ` ```json ... ``` `) instead of raw JSON? We need a robust "JSON extractor" utility.
- **Context Window:** If an email thread is very long, how much of the "Body" do we send? (Apps Script used 2000 chars; we should stick to this or increase it if the LLM allows).

### 2. Gmail Threading vs. Messages
- **Current logic:** Labels the *thread* but appends the *message* to the sheet.
- **Detail:** If a recruiter replies to an existing thread, should we append the new message too? The current Apps Script checks `existingMessageIds`, so it handles this correctly. We must replicate this logic.

### 3. Google API Quotas
- **Rate Limiting:** `gspread` and Gmail API have "Requests per minute" limits. For a large "catch-up" run (e.g., 200 unread emails), we might hit these.
- **Detail:** Should we implement a small `asyncio.sleep` between batch operations or just rely on backoff retries?

### 4. Logging & Monitoring
- **Verbosity:** Since it runs in the background via cron, we need structured logging (e.g., `SUCCESS: Labeled 5, Skipped 12, Errors 0`).
- **Failure Notification:** If authentication fails or the LLM is down, how will you know? (Option: Local desktop notification or simply checking the `run.log`).

### 5. Content Sanitization
- **Detail:** The original script uses `getPlainBody()`. We should ensure we strip HTML tags and excessive whitespace to save LLM tokens and improve classification accuracy.

### 6. Initial Setup (The "First Run")
- **Detail:** The very first time the script runs, it will search `newer_than:7d`. We need to ensure the Google Sheet exists or create it automatically if missing.

**Next Step:** Once these details are acknowledged, we can begin scaffolding the project structure and the `.env` / Auth setup.
