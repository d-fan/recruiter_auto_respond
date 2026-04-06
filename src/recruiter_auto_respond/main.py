import argparse
import asyncio
import logging
from dataclasses import dataclass
from typing import Any

from recruiter_auto_respond.config import settings
from recruiter_auto_respond.gmail_client import GmailClient
from recruiter_auto_respond.google_auth import get_google_services_async
from recruiter_auto_respond.llm_client import LLMClient
from recruiter_auto_respond.sheets_client import SheetsClient
from recruiter_auto_respond.state_manager import StateManager
from recruiter_auto_respond.utils import iso_to_ms, iso_to_unix, ms_to_iso


@dataclass
class PipelineClients:
    """Container for pipeline clients."""

    gmail: GmailClient
    sheets: SheetsClient
    llm: LLMClient
    label_id: str


async def setup_clients() -> tuple[GmailClient, SheetsClient, LLMClient] | None:
    """Initialize all necessary clients."""
    try:
        gmail_service, sheets_service = await get_google_services_async(
            settings.GOOGLE_APPLICATION_CREDENTIALS
        )
        return (
            GmailClient(gmail_service),
            SheetsClient(sheets_service),
            LLMClient(settings.LLM_API_URL, settings.LLM_API_KEY),
        )
    except Exception:
        logging.exception("Failed to initialize clients")
        return None


async def classify_and_record(
    m: dict[str, Any],
    clients: PipelineClients,
    dry_run: bool,
    stop_event: asyncio.Event,
) -> tuple[dict[str, Any] | None, bool]:
    """Process a single message: fetch body, classify, and label if needed.

    Returns (sheets_row_data, success).
    """
    logger = logging.getLogger(__name__)
    if stop_event.is_set():
        return None, False

    message_id = m["id"]
    thread_id = m["threadId"]
    msg_ts_iso = ms_to_iso(int(m["internalDate"]))

    try:
        body = await clients.gmail.fetch_message_body(message_id)
        is_recruiter = await clients.llm.classify_message(body)

        if is_recruiter:
            if not dry_run:
                await clients.gmail.add_label(message_id, clients.label_id)
                logger.info(f"Labeled message {message_id} as Recruiter.")
            else:
                logger.info(f"[DRY-RUN] Would label message {message_id} as Recruiter.")

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
        stop_event.set()
        return None, False


async def run_pipeline(
    clients: PipelineClients,
    messages: list[dict[str, Any]],
    state_manager: StateManager,
    dry_run: bool,
) -> None:
    """Run the core pipeline logic."""
    logger = logging.getLogger(__name__)
    stop_event = asyncio.Event()

    process_tasks = [
        classify_and_record(m, clients, dry_run, stop_event) for m in messages
    ]
    results = await asyncio.gather(*process_tasks)

    # Watermark logic: we only update up to the first failure
    rows_to_sync = []
    watermark_input = []
    for m, (row, success) in zip(messages, results, strict=True):
        if not success and not stop_event.is_set():
            # This should not happen since classify_and_record sets stop_event on error
            pass

        msg_ts_iso = ms_to_iso(int(m["internalDate"]))

        if stop_event.is_set() and not success and not row:
             # Stop adding to watermark if we hit a hard stop
             break

        if row:
            rows_to_sync.append(row)
        watermark_input.append((msg_ts_iso, success))

        if not success:
            break

    # Late-Sync Drift Protection
    if rows_to_sync and not dry_run:
        logger.info("Performing late-sync drift check...")
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

    # Update local state / watermark
    logger.info("Updating local state...")
    new_watermark = await state_manager.update_watermark(watermark_input)
    logger.info(f"New watermark: {new_watermark}")


async def main() -> None:
    """Main orchestrator for the AI Recruiter Labeler."""
    parser = argparse.ArgumentParser(description="Recruiter Auto-Respond Pipeline")
    parser.add_argument("--dry-run", action="store_true", help="Perform dry run")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    logger = logging.getLogger(__name__)
    logger.info("Starting pipeline...")

    state_manager = StateManager(settings.STATE_FILE)
    state = await state_manager.load_state()
    last_run_iso = state.last_run_timestamp
    logger.info(f"Last run: {last_run_iso}")

    raw_clients = await setup_clients()
    if not raw_clients:
        return
    gmail_client, sheets_client, llm_client = raw_clients

    try:
        last_run_unix = iso_to_unix(last_run_iso)
        last_run_ms = iso_to_ms(last_run_iso)

        query = f'-label:"{settings.GMAIL_LABEL_NAME}" after:{last_run_unix}'
        messages = await gmail_client.fetch_messages(query)
        if not messages:
            logger.info("No new messages.")
            return

        metadata_tasks = [
            gmail_client.fetch_message_metadata(m["id"]) for m in messages
        ]
        with_meta = await asyncio.gather(*metadata_tasks)

        to_process = sorted(
            [m for m in with_meta if int(m["internalDate"]) > last_run_ms],
            key=lambda m: int(m["internalDate"]),
        )

        if not to_process:
            logger.info("No new messages after filtering.")
            return

        label_id = await gmail_client.get_or_create_label(settings.GMAIL_LABEL_NAME)

        clients = PipelineClients(
            gmail=gmail_client,
            sheets=sheets_client,
            llm=llm_client,
            label_id=label_id,
        )
        await run_pipeline(clients, to_process, state_manager, args.dry_run)

    finally:
        await llm_client.close()


if __name__ == "__main__":
    asyncio.run(main())
