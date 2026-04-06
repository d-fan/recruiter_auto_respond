import argparse
import asyncio
import logging
from dataclasses import dataclass
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
        llm_client = LLMClient(settings.LLM_API_URL, settings.LLM_API_KEY)
        logger.info("Clients initialized successfully.", extra={"phase": "setup"})
        return gmail_client, sheets_client, llm_client
    except Exception:
        logger.exception("Failed to initialize clients", extra={"phase": "setup"})
        return None


@dataclass
class PipelineClients:
    """Container for pipeline clients."""
    gmail: GmailClient
    sheets: SheetsClient
    llm: LLMClient
    label_id: str


async def classify_and_record(
    m: dict[str, Any],
    clients: PipelineClients,
    semaphore: asyncio.Semaphore,
    dry_run: bool,
) -> tuple[dict[str, Any] | None, bool]:
    """Process a single message: fetch body, classify, and label if needed.

    Returns (sheets_row_data, success).
    """
    logger = logging.getLogger(__name__)
    message_id = m["id"]
    thread_id = m["threadId"]
    internal_date = int(m["internalDate"])
    msg_dt = datetime.fromtimestamp(internal_date / 1000, tz=timezone.utc)
    msg_ts_iso = msg_dt.strftime("%Y-%m-%dT%H:%M:%SZ")

    try:
        async with semaphore:
            # Fetch body
            body = await clients.gmail.fetch_message_body(message_id)

            # Classify
            is_recruiter = await clients.llm.classify_message(body)

        if is_recruiter:
            if not dry_run:
                await clients.gmail.add_label(message_id, clients.label_id)
                logger.info(f"Labeled message {message_id} as Recruiter.")
            else:
                logger.info(f"[DRY-RUN] Would label message {message_id} as Recruiter.")

            # Prepare row for Sheets: Thread ID, Message ID, Date
            row = {
                "threadId": thread_id,
                "messageId": message_id,
                "timestamp": msg_ts_iso,
            }
            return row, True

        logger.info(f"Skipped message {message_id} (Not Recruiter).")
        return None, True

    except Exception:
        logger.exception(f"Failed to process message {message_id}")
        return None, False


async def run_pipeline(
    clients: PipelineClients,
    messages_with_metadata: list[dict[str, Any]],
    state_manager: StateManager,
    dry_run: bool,
) -> None:
    """Run the core pipeline logic."""
    logger = logging.getLogger(__name__)

    # 5. Process messages in parallel
    logger.info("Processing messages...", extra={"phase": "phase-4"})
    semaphore = asyncio.Semaphore(settings.PARALLEL_LIMIT)

    process_tasks = [
        classify_and_record(m, clients, semaphore, dry_run)
        for m in messages_with_metadata
    ]

    results = await asyncio.gather(*process_tasks)

    rows_to_sync = [row for row, success in results if row]
    watermark_input = []

    for m, (_, success) in zip(messages_with_metadata, results, strict=True):
        msg_dt = datetime.fromtimestamp(int(m["internalDate"]) / 1000, tz=timezone.utc)
        msg_ts_iso = msg_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        watermark_input.append((msg_ts_iso, success))

    # 6. Late-Sync Drift Protection
    if rows_to_sync and not dry_run:
        logger.info("Performing late-sync drift check...", extra={"phase": "phase-5"})
        existing_ids = await clients.sheets.get_message_ids(settings.GOOGLE_SHEET_ID)
        filtered_rows = [r for r in rows_to_sync if r["messageId"] not in existing_ids]

        if filtered_rows:
            logger.info(f"Syncing {len(filtered_rows)} rows to Sheets.")
            sync_data = [
                [r["threadId"], r["messageId"], r["timestamp"]] for r in filtered_rows
            ]
            await clients.sheets.append_rows(settings.GOOGLE_SHEET_ID, sync_data)
        else:
            logger.info("All messages already present in Sheets. Skipping sync.")
    elif dry_run:
        logger.info("[DRY-RUN] Skipping Sheets sync.")

    # 7. Update local state / watermark
    logger.info("Updating local state...", extra={"phase": "phase-6"})
    new_watermark = await state_manager.update_watermark(watermark_input)
    logger.info(f"New watermark: {new_watermark}", extra={"phase": "phase-6"})


async def main() -> None:
    """Main orchestrator for the AI Recruiter Labeler & Syncer."""
    parser = argparse.ArgumentParser(description="Recruiter Auto-Respond Pipeline")
    parser.add_argument("--dry-run", action="store_true", help="Perform dry run")
    args = parser.parse_args()

    logger = logging.getLogger(__name__)
    logger.info("Starting the pipeline...", extra={"phase": "setup"})

    # 1. Load configuration and state
    state_file = getattr(settings, "STATE_FILE", "state.json")
    state_manager = StateManager(state_file)
    state = await state_manager.load_state()
    last_run_iso = state.get("last_run_timestamp", "1970-01-01T00:00:00Z")
    logger.info(f"Last run: {last_run_iso}", extra={"phase": "phase-1"})

    try:
        dt = datetime.fromisoformat(last_run_iso.replace("Z", "+00:00"))
        last_run_unix = int(dt.timestamp())
    except ValueError:
        last_run_unix = 0

    # Initialize Clients
    raw_clients = await setup_clients()
    if not raw_clients:
        return
    gmail_client, sheets_client, llm_client = raw_clients

    # 2. Fetch messages from Gmail
    logger.info("Fetching new messages from Gmail...", extra={"phase": "phase-2"})
    query = f'-label:"{settings.GMAIL_LABEL_NAME}" after:{last_run_unix}'
    messages = await gmail_client.fetch_messages(query)
    logger.info(f"Found {len(messages)} matching messages.", extra={"phase": "phase-2"})

    if not messages:
        logger.info("No new messages to process.", extra={"phase": "setup"})
        return

    # 3. Fetch metadata for sorting
    logger.info("Fetching metadata for sorting...", extra={"phase": "phase-3"})
    metadata_tasks = [gmail_client.fetch_message_metadata(m["id"]) for m in messages]
    messages_with_metadata = await asyncio.gather(*metadata_tasks)
    messages_with_metadata.sort(key=lambda m: int(m["internalDate"]))

    # 4. Get label ID
    label_id = await gmail_client.get_or_create_label(settings.GMAIL_LABEL_NAME)

    # 5-7. Run Pipeline
    clients = PipelineClients(
        gmail=gmail_client,
        sheets=sheets_client,
        llm=llm_client,
        label_id=label_id,
    )
    await run_pipeline(clients, messages_with_metadata, state_manager, args.dry_run)
    logger.info("Pipeline complete.", extra={"phase": "setup"})

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    asyncio.run(main())
