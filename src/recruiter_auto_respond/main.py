import asyncio
import logging

from recruiter_auto_respond.config import settings
from recruiter_auto_respond.gmail_client import GmailClient
from recruiter_auto_respond.google_auth import get_google_services_async
from recruiter_auto_respond.sheets_client import SheetsClient
from recruiter_auto_respond.state_manager import StateManager


async def main() -> None:
    """Main orchestrator for the AI Recruiter Labeler & Syncer."""
    logger = logging.getLogger(__name__)
    logger.info("Starting the pipeline...", extra={"phase": "setup"})

    # 1. Load configuration and state
    state_file = getattr(settings, "STATE_FILE", "state.json")
    logger.info(f"Using state file: {state_file}", extra={"phase": "phase-1"})
    state_manager = StateManager(state_file)
    state = await state_manager.load_state()
    last_run = state.get("last_run_timestamp", "1970-01-01T00:00:00Z")
    logger.info(f"Last run: {last_run}", extra={"phase": "phase-1"})

    # Initialize Google Services
    try:
        gmail_service, sheets_service = await get_google_services_async(
            settings.GOOGLE_APPLICATION_CREDENTIALS
        )
        gmail_client = GmailClient(gmail_service)  # noqa: F841
        sheets_client = SheetsClient(sheets_service)  # noqa: F841
        logger.info(
            "Google services initialized successfully.", extra={"phase": "setup"}
        )
    except Exception:
        logger.exception(
            "Failed to initialize Google services", extra={"phase": "setup"}
        )
        return

    # 2. Fetch messages from Gmail
    logger.info(
        "Fetching new messages from Gmail...", extra={"phase": "phase-2"}
    )
    # query = f"-label:\"{settings.GMAIL_LABEL_NAME}\" after:{last_run}"
    # messages = await gmail_client.fetch_messages(query)

    # 3. Classify with LLM
    logger.info("Classifying messages with LLM...", extra={"phase": "phase-3"})

    # 4. Update Gmail labels
    logger.info("Updating Gmail labels...", extra={"phase": "phase-4"})

    # 5. Sync results to Google Sheets
    logger.info(
        "Syncing results to Google Sheets...", extra={"phase": "phase-5"}
    )

    # 6. Update local state
    logger.info("Updating local state...", extra={"phase": "phase-6"})

    logger.info("Pipeline complete.", extra={"phase": "setup"})


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    asyncio.run(main())
