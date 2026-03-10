import asyncio
import logging

from recruiter_auto_respond.config import settings


async def main() -> None:
    """Main orchestrator for the AI Recruiter Labeler & Syncer."""
    logger = logging.getLogger(__name__)
    logger.info("Starting the pipeline...", extra={"phase": "setup"})

    # 1. Load configuration and state
    logger.info(
        f"Using state file: {settings.STATE_FILE}", extra={"phase": "phase-1"}
    )

    # 2. Fetch messages from Gmail
    logger.info("Fetching new messages from Gmail...", extra={"phase": "phase-2"})

    # 3. Classify with LLM
    logger.info("Classifying messages with LLM...", extra={"phase": "phase-3"})

    # 4. Update Gmail labels
    logger.info("Updating Gmail labels...", extra={"phase": "phase-4"})

    # 5. Sync results to Google Sheets
    logger.info("Syncing results to Google Sheets...", extra={"phase": "phase-5"})

    # 6. Update local state
    logger.info("Updating local state...", extra={"phase": "phase-6"})

    logger.info("Pipeline complete.", extra={"phase": "setup"})


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    asyncio.run(main())
