# Google Apps Script to Python Conversion Plan: AI Recruiter Labeler & Syncer

This document outlines the strategy for migrating the `appscript.js` functionality into a robust Python application.

## 1. Feature Analysis (Current State)
The existing Apps Script performs several key tasks:
- **Search:** Queries Gmail for unread emails matching specific recruiter-like criteria.
- **Classification:** Sends email content (subject + body) to a self-hosted LLM API.
- **Action:** Labels positive matches in Gmail.
- **Sync:** Appends metadata of labeled emails to a Google Sheet, avoiding duplicates.
- **State Management:** Uses `PropertiesService` to track the last run's timestamp and implements a "worker pool" for parallel API calls.

## 2. Technical Requirements
To replicate this in Python, we will need:
- **Gmail API Access:** Requires a Google Cloud Project with the Gmail API enabled and OAuth2 credentials (`credentials.json`).
- **Google Sheets API Access:** Requires the Sheets API enabled (using `gspread` or the official client).
- **LLM Client:** `httpx` or `requests` for the custom API endpoint.
- **Scheduler:** `cron`, `systemd`, or a Python-based scheduler like `schedule` or `APScheduler`.

---

## 3. Implementation Options

### Option A: The "Surgical" CLI Port (Sync/Threaded)
A straightforward port using standard Google client libraries and Python threads for parallelism.
- **Stack:** `google-api-python-client`, `google-auth-oauthlib`, `requests`, `concurrent.futures`.
- **Tradeoffs:**
  - **Pros:** Easiest to debug; very similar structure to the original script.
  - **Cons:** Threading in Python is heavier than `asyncio` for I/O; synchronous Google API calls can be slow.

### Option B: The "Modern Async" Service (Recommended)
An asynchronous implementation leveraging Python's `asyncio` for high-performance I/O.
- **Stack:** `httpx` (for LLM), `aiogmail` (or custom `asyncio` wrappers), `gspread-asyncio`.
- **Tradeoffs:**
  - **Pros:** Extremely efficient at handling the "worker pool" pattern; lower resource footprint.
  - **Cons:** More complex code (async/await boilerplate); library support for async Google APIs is less "official."

### Option C: The "Robust Data" Approach (SQLite + Docker)
Adds a local database to track state instead of relying purely on Gmail labels/Sheet checks.
- **Stack:** `sqlite3`, `google-api-python-client`, `Docker`.
- **Tradeoffs:**
  - **Pros:** Most resilient to failures; prevents duplicate processing even if labels are manually moved; easy to deploy to a NAS or VPS.
  - **Cons:** Most moving parts; requires managing a local database file.

---

## 4. Key Tradeoff Comparison

| Feature | Apps Script (Current) | Python Option A | Python Option B | Python Option C |
| :--- | :--- | :--- | :--- | :--- |
| **Auth** | Built-in (Automatic) | OAuth2 (Manual setup) | OAuth2 (Manual setup) | Service Account / OAuth2 |
| **Parallelism** | Worker Pool (URLFetch) | `ThreadPoolExecutor` | `asyncio.gather` | `asyncio.gather` |
| **State** | Script Properties | JSON file | JSON/YAML file | SQLite Database |
| **Deployment** | Google Cloud (Free) | Local / VPS / Cron | Long-running Process | Docker Container |
| **Speed** | 6m Timeout Limit | Unbound | Extremely Fast | Fast + Reliable |

---

## 5. Proposed Migration Strategy

1.  **Phase 1: Authentication & Discovery**
    - Set up a Google Cloud Project and download `credentials.json`.
    - Create a small script to verify Gmail and Sheets connectivity.
2.  **Phase 2: The Core Logic**
    - Implement the Gmail search and LLM classification logic.
    - Replicate the "checkpointing" logic using a local `state.json` or SQLite.
3.  **Phase 3: Sheet Synchronization**
    - Use `gspread` to replicate the spreadsheet appending logic.
4.  **Phase 4: Automation**
    - Package the script for deployment (e.g., Dockerfile or systemd timer).

## 6. Security Considerations
- **Credentials:** Move `LLM_API_KEY`, `LLM_USER`, and `LLM_PASS` from Apps Script Properties to a `.env` file.
- **Token Storage:** Ensure `token.json` (the OAuth2 refresh token) is stored securely and excluded from Git.
