import asyncio
import logging
from typing import Any

from recruiter_auto_respond.config import settings
from recruiter_auto_respond.gmail_client import GmailClient
from recruiter_auto_respond.google_auth import get_google_services_async
from recruiter_auto_respond.llm_client import LLMClient
from recruiter_auto_respond.sheets_client import SheetsClient
from recruiter_auto_respond.state_manager import StateManager
from recruiter_auto_respond.utils import iso_to_ms, iso_to_unix, ms_to_iso


async def setup_clients() -> tuple[GmailClient, SheetsClient, LLMClient] | None:
    """Initialize all necessary clients."""
    try:
        gmail_service, sheets_service = await get_google_services_async(
            settings.GOOGLE_APPLICATION_CREDENTIALS
        )
        return (
            GmailClient(gmail_service),
            SheetsClient(sheets_service),
            LLMClient(settings.LLM_API_URL),
        )
    except Exception:
        logging.exception("Failed to initialize clients")
        return None


async def process_messages(
    messages: list[dict[str, Any]],
    gmail_client: GmailClient,
    llm_client: LLMClient,
    label_id: str,
) -> list[tuple[str, bool]]:
    """Process messages in parallel, stopping on the first failure."""
    logger = logging.getLogger(__name__)
    stop_event = asyncio.Event()

    async def _process_single(m: dict[str, Any]) -> tuple[str, bool]:
        if stop_event.is_set():
            return "", False

        message_id = m["id"]
        msg_ts_iso = ms_to_iso(int(m["internalDate"]))

        try:
            body = await gmail_client.fetch_message_body(message_id)
            if await llm_client.classify_message(body):
                await gmail_client.add_label(message_id, label_id)
                logger.info(f"Labeled message {message_id} as Recruiter.")
            else:
                logger.info(f"Skipped message {message_id} (Not Recruiter).")
            return msg_ts_iso, True
        except Exception:
            logger.exception(f"Failed to process message {message_id}")
            stop_event.set()
            return "", False

    gathered = await asyncio.gather(*[_process_single(m) for m in messages])

    results: list[tuple[str, bool]] = []
    for ts, success in gathered:
        if not ts:
            break
        results.append((ts, success))
    return results


async def main() -> None:
    """Main orchestrator for the AI Recruiter Labeler."""
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

    clients = await setup_clients()
    if not clients:
        return
    gmail_client, _sheets_client, llm_client = clients

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

        # Precise filtering and sorting
        to_process = sorted(
            [m for m in with_meta if int(m["internalDate"]) > last_run_ms],
            key=lambda m: int(m["internalDate"]),
        )

        if not to_process:
            logger.info("No new messages after filtering.")
            return

        label_id = await gmail_client.get_or_create_label(settings.GMAIL_LABEL_NAME)
        results = await process_messages(to_process, gmail_client, llm_client, label_id)

        new_watermark = await state_manager.update_watermark(results)
        logger.info(f"New watermark: {new_watermark}")

    finally:
        await llm_client.close()


if __name__ == "__main__":
    asyncio.run(main())
