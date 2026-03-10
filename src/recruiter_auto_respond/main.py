import asyncio
import logging

from recruiter_auto_respond.config import settings


async def main() -> None:
    """Main orchestrator for the AI Recruiter Labeler & Syncer."""
    logging.info("Starting the pipeline...")

    # 1. Load configuration and state
    logging.info("Phase 1: Loading configuration and state...")
    _ = settings
    logging.info(f"Using state file: {settings.STATE_FILE}")

    # 2. Fetch messages from Gmail
    logging.info("Phase 2: Fetching new messages from Gmail...")

    # 3. Classify with LLM
    logging.info("Phase 3: Classifying messages with LLM...")

    # 4. Update Gmail labels
    logging.info("Phase 4: Updating Gmail labels...")

    # 5. Sync results to Google Sheets
    logging.info("Phase 5: Syncing results to Google Sheets...")

    # 6. Update local state
    logging.info("Phase 6: Updating local state...")

    logging.info("Pipeline complete.")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    asyncio.run(main())
