# Design Plan: AI Recruiter Labeler & Syncer (Python Async)

This document outlines the architectural design for migrating `appscript.js` to a high-performance Python application using **Option B: Modern Async**.

## 1. Selected Architecture: Option B (Modern Async)
We will use Python's `asyncio` to manage high-concurrency I/O operations (Gmail API, LLM calls, and Sheets API). This allows us to replicate the original script's "worker pool" behavior more efficiently.

### Key Stack
- **Runtime:** Python 3.10+
- **HTTP Client:** `httpx` (Asynchronous HTTP requests)
- **Gmail API:** `google-api-python-client` (with thread-pool executors) OR `aiogmail`.
- **Sheets API:** `gspread-asyncio` or `aiosheets`.
- **Concurrency Control:** `asyncio.Semaphore` to limit parallel LLM requests (replaces `PARALLEL_LIMIT`).

## 2. Component Design & Options

### A. Authentication & Secret Management
**Goal:** Securely manage Google OAuth2 tokens and LLM credentials.
- **Option 1 (Local `.env`):** Simple and effective for personal use. Store `LLM_API_KEY` and `credentials.json` path in a `.env` file.
- **Option 2 (Environment Variables + Docker Secrets):** Better for production/server deployments.
- **Requirement:** A `TokenManager` class to handle OAuth2 flow and automatically refresh `token.json`.

### B. State Management (Checkpointing)
**Goal:** Persistently track the `last_run_timestamp` and processed message IDs.
- **Option 1 (Simple JSON):** A `state.json` file. Easy to read/edit manually.
- **Option 2 (SQLite - Recommended):** A lightweight database. 
  - *Pros:* Atomic writes prevent corruption; can store a history of every classification for later analysis/fine-tuning.
  - *Cons:* Slightly more boilerplate.
- **Decision:** We will use **Option 2 (SQLite)** to ensure data integrity and track `message_id`s to prevent duplicate sheet entries.

### C. Gmail API Integration
**Goal:** Fetch unread threads and apply labels.
- **Approach:** 
  1. `list_threads` with the search query.
  2. `get_thread` for content extraction.
  3. `batch_modify` to apply labels to multiple threads at once (optimizing API calls).
- **Concurrency:** Use `asyncio.gather` for fetching thread details, but rate-limit to avoid Google API quota limits.

### D. LLM Processing Pipeline
**Goal:** Classify emails using the external LLM.
- **Design:**
  - Create a `Classifier` class.
  - Use an `asyncio.Semaphore(10)` to maintain exactly 10 concurrent requests (matching `PARALLEL_LIMIT`).
  - Implement **exponential backoff** for 5xx errors or rate-limiting from the LLM provider.

### E. Spreadsheet Synchronization
**Goal:** Append new recruiter emails to the "Emails" sheet.
- **Strategy:** 
  - **Batch Update (Recommended):** Collect all positive matches from a single run and perform one `append_rows` call. This is significantly faster and safer than row-by-row appending.
  - **Deduplication:** Verify the `message_id` against the SQLite database *before* appending to the sheet.

## 3. Workflow Diagram (Internal)

1.  **Initialize:** Load `.env`, Authenticate Google APIs, Open SQLite connection.
2.  **Fetch:** Query Gmail for `is:unread -label:"! Jobs/2026"`.
3.  **Process (Concurrent):**
    - For each thread:
      - Extract content (Subject + first 2000 chars of Body).
      - Check SQLite: If already processed, skip.
      - Send to LLM via `httpx`.
      - If `isRecruiter`: Add to `positive_matches` list.
4.  **Action (Batch):**
    - Apply Gmail labels to all `positive_matches`.
    - Format metadata for Google Sheets.
    - Append to Sheets in one batch operation.
    - Update `last_run_timestamp` in SQLite.
5.  **Cleanup:** Close connections and log summary.

## 4. Error Handling Strategy

| Scenario | Action |
| :--- | :--- |
| **LLM Timeout** | Retry up to 3 times with backoff, then log and skip. |
| **Google Auth Expired** | Attempt silent refresh; if fail, stop and notify (log error). |
| **Sheets API Quota** | Pause and retry (exponential backoff). |
| **Partial Success** | Only update `last_run_timestamp` if all emails in that batch were processed successfully (Checkpointing). |

## 5. Deployment Options

- **Option 1: Systemd Timer (Linux):** Runs the script every 30 minutes. Cleanest for a dedicated server.
- **Option 2: Docker + Cron:** High portability.
- **Option 3: GitHub Actions:** Can run on a schedule for free, but requires careful management of the persistent `token.json` and SQLite file (e.g., uploading them as artifacts or using a remote DB).

**Next Step:** Once the design is approved, we will begin Phase 1: Authentication and Base Client Setup.
