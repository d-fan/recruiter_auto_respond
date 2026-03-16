# Agent Hand-off: Manual Gmail Testing Interface

## Current Status

We have successfully implemented the foundation of the AI Recruiter Labeler & Syncer. The following components are complete and verified via unit/conformance tests and linting:

- **Project Structure:** Industry-standard `src` layout with strict Mypy and Ruff configuration.
- **Config & Logging:** Robust `.env` loading via `pydantic-settings` and structured logging in `main.py`.
- **Google API Clients:** `GmailClient` and `SheetsClient` are implemented with `asyncio.to_thread` wrappers and `tenacity` retries.
- **Authentication:** OAuth2 flow with `google_auth.py` providing an async initialization wrapper.
- **CI/CD:** `pre-commit` hooks configured for linting, formatting, and type checking.

## Next Task: Manual Gmail Verification

Implement a mechanism to manually execute and verify `GmailClient` operations. This is for developer verification before the full pipeline integration.

### Requirements:

1. **Interface:** Create a **standalone script** (e.g., `src/recruiter_auto_respond/scripts/manual_gmail_verify.py`).
2. **Configuration:** Use the production `.env` settings via the existing `Settings` class.
3. **Input Method:** Hardcode the `search_query` and `message_id` with obvious placeholders (e.g., `"YOUR_QUERY_HERE"`, `"YOUR_MSG_ID_HERE"`) for the user to fill in.
4. **Functionality:**
   - Fetch a list of messages based on the query.
   - Fetch the decoded body of a specific message ID.
5. **Output Format:**
   - If the function returns a structured object (list/dict), print it as pretty-printed JSON.
   - If the function returns a string (the message body), print it as raw text.

### Interface Tradeoffs:

- **Standalone Script (Selected):** Decouples verification from the production entry point and avoids CLI parsing complexity in `main.py`.
- **CLI Subcommand:** More integrated for long-term maintenance but adds significant boilerplate to `main.py` for a temporary verification task.
- **REPL/Notebook:** Requires the user to manually copy-paste boilerplate for auth and client setup, reducing repeatability.

## Files of Interest

- `src/recruiter_auto_respond/gmail_client.py`: The implementation to be tested.
- `src/recruiter_auto_respond/google_auth.py`: Used to obtain the authenticated service.
- `src/recruiter_auto_respond/main.py`: Reference for current configuration and logging setup.
- `tests/test_gmail_client.py`: reference for expected data shapes and mocks.
