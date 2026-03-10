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
- **CLI Policy:** Avoid chaining multiple commands, e.g. `python -m venv .venv && echo pytest > requirements.txt`. Run commands one at a time.
- **File Edit Policy:** Avoid using command line tools to make file changes unless the contents must come from another command's output. Edit or create the file directly.

## Project Context
- **Source Material:** `appscript.js` contains the original logic. Reference it for prompt engineering and business rules.
- **Roadmap:** Refer to Github Issues for current implementation status.

## Design choices
- **Library Selection:** When evaluating options for different libraries for the same behavior, justify the choice in detail. This may include presenting usage examples for each and demonstrating why one is more ergonomic for developers, providing examples where one library would fall short in the future, comparing package sizes and transitive dependencies, etc.

## Development
- **Conformance Test:** When adding external API calls with an untyped library, add a standalone test that checks that the API result has the expected structure. Use the test output to inform unit test mocks.
- **Test Driven Development:** First add unit tests, potentially with mock data following the structure of the output of the conformance tests, run those tests to verify that those tests fail, commit those changes, write the actual implementation, then iterate until the tests pass.
- **Test API calls:** Other than conformance tests, unit tests should not make API calls. Calls and results should be mocked, and interfaces structured to make mocking easy.
- **Test Changes:** Removing tests or changing the assertion of tests should not be done without explicit user approval. When doing so, it should not happen alongside any implementation changes. Update the test, then after the user allows the file change, update the impemenation. Adding new test cases is always allowed, and should be done when appropriate.

## Workflow
- **Commits:** Make sure to commit frequently, especially when making intermediate progress for an issue or feature.
- **Branches/PRs:** Create new feature branches for every issue. Create a Pull Request when changes are ready to review and merge. The repository is configured to automatically request a review from Github Copilot upon Pull Request creation. You do not need to request a review.
- **PR Comments:** If making substantive changes to the PR, re-request a review from Github Copilot. For small tweaks, no re-reviews are needed.
- **Completed Issues:** Do not move on to the next issue until the user tells you to do so.
- **Linking Issues:** Always link PRs to the relevant Issue, if such an issue exists.
- **Closing Issues:** If asked to work on an Issue that is already completed but has not yet been closed, suggest to the user to close, and close it yourself if they agree.