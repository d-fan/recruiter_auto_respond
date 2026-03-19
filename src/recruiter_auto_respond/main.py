import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

from recruiter_auto_respond.config import settings
from recruiter_auto_respond.gmail_client import GmailClient
from recruiter_auto_respond.google_auth import get_google_services_async
from recruiter_auto_respond.llm_client import LLMClient
from recruiter_auto_respond.sheets_client import SheetsClient
from recruiter_auto_respond.state_manager import StateManager


async def setup_clients() -> tuple[GmailClient, SheetsClient, LLMClient] | None:
    """Initialize all necessary clients."""
    logger = logging.getLogger(__name__)
    try:
        gmail_service, sheets_service = await get_google_services_async(
            settings.GOOGLE_APPLICATION_CREDENTIALS
        )
        gmail_client = GmailClient(gmail_service)
        sheets_client = SheetsClient(sheets_service)
        llm_client = LLMClient(settings.LLM_API_URL)
        logger.info("Clients initialized successfully.", extra={"phase": "setup"})
        return gmail_client, sheets_client, llm_client
    except Exception:
        logger.exception("Failed to initialize clients", extra={"phase": "setup"})
        return None


async def process_messages(
    messages_with_metadata: list[dict[str, Any]],
    gmail_client: GmailClient,
    llm_client: LLMClient,
    label_id: str,
) -> list[tuple[str, bool]]:
    """Process messages one by one and return results."""
    logger = logging.getLogger(__name__)
    results: list[tuple[str, bool]] = []

    for m in messages_with_metadata:
        message_id = m["id"]
        # Convert internalDate (ms) to ISO format
        msg_dt = datetime.fromtimestamp(int(m["internalDate"]) / 1000, tz=timezone.utc)
        msg_ts_iso = msg_dt.strftime("%Y-%m-%dT%H:%M:%SZ")

        try:
            # 5a. Fetch body
            body = await gmail_client.fetch_message_body(message_id)

            # 5b. Classify
            is_recruiter = await llm_client.classify_message(body)

            # 5c. Label if match
            if is_recruiter:
                await gmail_client.add_label(message_id, label_id)
                logger.info(f"Labeled message {message_id} as Recruiter.")
            else:
                logger.info(f"Skipped message {message_id} (Not Recruiter).")

            # Record success (labeled or determined not to label)
            results.append((msg_ts_iso, True))

        except Exception:
            logger.exception(f"Failed to process message {message_id}")
            # Stop processing further messages to respect hard-stop
            break
    return results


async def main() -> None:
    """Main orchestrator for the AI Recruiter Labeler & Syncer."""
    logger = logging.getLogger(__name__)
    logger.info("Starting the pipeline...", extra={"phase": "setup"})

    # 1. Load configuration and state
    state_file = getattr(settings, "STATE_FILE", "state.json")
    logger.info(f"Using state file: {state_file}", extra={"phase": "phase-1"})
    state_manager = StateManager(state_file)
    state = await state_manager.load_state()
    last_run_iso = state.get("last_run_timestamp", "1970-01-01T00:00:00Z")
    logger.info(f"Last run: {last_run_iso}", extra={"phase": "phase-1"})

    # Convert ISO to Unix timestamp for Gmail query
    try:
        dt = datetime.fromisoformat(last_run_iso.replace("Z", "+00:00"))
        last_run_unix = int(dt.timestamp())
    except ValueError:
        logger.warning(f"Invalid last_run_timestamp: {last_run_iso}, defaulting to 0")
        last_run_unix = 0

    # Initialize Clients
    clients = await setup_clients()
    if not clients:
        return
    gmail_client, _sheets_client, llm_client = clients

    # 2. Fetch messages from Gmail
    logger.info("Fetching new messages from Gmail...", extra={"phase": "phase-2"})
    query = f'-label:"{settings.GMAIL_LABEL_NAME}" after:{last_run_unix}'
    messages = await gmail_client.fetch_messages(query)
    logger.info(
        f"Found {len(messages)} matching messages.", extra={"phase": "phase-2"}
    )

    if not messages:
        logger.info("No new messages to process.", extra={"phase": "setup"})
        return

    # 3. Fetch metadata for sorting
    logger.info("Fetching metadata for sorting...", extra={"phase": "phase-3"})
    metadata_tasks = [gmail_client.fetch_message_metadata(m["id"]) for m in messages]
    messages_with_metadata = await asyncio.gather(*metadata_tasks)

    # Sort oldest to newest
    messages_with_metadata.sort(key=lambda m: int(m["internalDate"]))

    # 4. Get label ID
    label_id = await gmail_client.get_or_create_label(settings.GMAIL_LABEL_NAME)

    # 5. Process messages
    logger.info("Processing messages...", extra={"phase": "phase-4"})
    results = await process_messages(
        messages_with_metadata, gmail_client, llm_client, label_id
    )

    # 6. Update local state / watermark
    logger.info("Updating local state...", extra={"phase": "phase-6"})
    new_watermark = await state_manager.update_watermark(results)
    logger.info(f"New watermark: {new_watermark}", extra={"phase": "phase-6"})

    logger.info("Pipeline complete.", extra={"phase": "setup"})


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    asyncio.run(main())
