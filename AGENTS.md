# Agent Instructions: Recruiter Auto-Respond

This project is currently a migration of a Google Apps Script to a high-performance Python application. There will be additional features added to this project after a successful migration.

## Technical Foundation
- **Language:** Python 3.10+
- **Style:** Strict type hints (PEP 484), Google-style docstrings, and `black` formatting.
- **Concurrency:** Mandatory use of `asyncio`. Avoid blocking I/O; use `asyncio.to_thread` for libraries that do not support async natively.
- **Error Handling:** Use `tenacity` for all external API calls (Gmail, Sheets, LLM). Implement exponential backoff.

## Critical Architectural Rules
1. **Watermark Checkpointing:** Progress is tracked by the date of the highest *consecutive* successful thread. Do not skip threads in `state.json`.
2. **Late-Sync Drift Protection:** Always fetch the 'Message ID' column from the Google Sheet immediately before writing to verify the message hasn't been added by another process or run.
3. **LLM Interaction:** Use `llama.cpp` OpenAI-compatible endpoints. Always enforce JSON mode for classification.

## Secrets & Safety
- **Never commit:** `credentials.json`, `token.json`, `.env`, or `state.json`.
- **Git Policy:** Do not stage or commit changes unless explicitly directed. Use `run_shell_command` to verify the environment (e.g., `.venv` activation) before suggesting implementations.
- **CLI Policy:** Avoid chaining multiple commands, e.g. `python -m venv .venv && echo pytest > requirements.txt`
- **File Edit Policy:** Avoid using command line tools to make file changes unless the contents must come from another command's output. Edit or create the file directly.

## Project Context
- **Source Material:** `appscript.js` contains the original logic. Reference it for prompt engineering and business rules.
- **Roadmap:** Refer to Github Issues for current implementation status.
