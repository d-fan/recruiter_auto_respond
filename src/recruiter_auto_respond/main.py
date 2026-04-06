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


class Pipeline:
    """Orchestrator for the AI Recruiter Labeler & Syncer."""

    def __init__(
        self,
        gmail_client: GmailClient,
        sheets_client: SheetsClient,
        llm_client: LLMClient,
        state_manager: StateManager,
        label_name: str,
    ) -> None:
        self.gmail_client = gmail_client
        self.sheets_client = sheets_client
        self.llm_client = llm_client
        self.state_manager = state_manager
        self.label_name = label_name
        self.logger = logging.getLogger(__name__)

    async def process_messages(
        self,
        messages_with_metadata: list[dict[str, Any]],
        label_id: str,
    ) -> list[tuple[str, bool]]:
        """Process messages in parallel and return results.

        Respects the "Hard Stop" requirement by stopping new work if a failure occurs.
        """
        stop_event = asyncio.Event()

        async def process_single(m: dict[str, Any]) -> tuple[str, bool]:
            if stop_event.is_set():
                # If a hard stop was triggered, we don't process further.
                return "", False

            message_id = m["id"]
            # Convert internalDate (ms) to ISO format with ms precision
            ms_timestamp = int(m["internalDate"])
            msg_dt = datetime.fromtimestamp(ms_timestamp / 1000, tz=timezone.utc)
            # Use ISO format with millisecond precision
            msg_ts_iso = msg_dt.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"

            try:
                # 5a. Fetch body
                body = await self.gmail_client.fetch_message_body(message_id)

                # 5b. Classify
                is_recruiter = await self.llm_client.classify_message(body)

                # 5c. Label if match
                if is_recruiter:
                    await self.gmail_client.add_label(message_id, label_id)
                    self.logger.info(f"Labeled message {message_id} as Recruiter.")
                else:
                    self.logger.info(f"Skipped message {message_id} (Not Recruiter).")

                # Return success status (True means processed without exception)
                return msg_ts_iso, True

            except Exception:
                self.logger.exception(f"Failed to process message {message_id}")
                stop_event.set()
                return "", False

        # Create tasks for all messages.
        tasks = [process_single(m) for m in messages_with_metadata]
        gathered_results = await asyncio.gather(*tasks)

        # Filter out results that weren't processed due to hard stop or failure
        results: list[tuple[str, bool]] = []
        for ts, success in gathered_results:
            if not ts:  # Indicates failure or hard stop
                break
            results.append((ts, success))

        return results

    async def run(self) -> None:
        """Run the full pipeline."""
        self.logger.info("Starting the pipeline...", extra={"phase": "setup"})

        # 1. Load state
        state = await self.state_manager.load_state()
        last_run_iso = state.get("last_run_timestamp", "1970-01-01T00:00:00.000Z")
        self.logger.info(f"Last run: {last_run_iso}", extra={"phase": "phase-1"})

        # Convert ISO to Unix timestamp
        try:
            dt = datetime.fromisoformat(last_run_iso.replace("Z", "+00:00"))
            last_run_unix_sec = int(dt.timestamp())
            last_run_ms = int(dt.timestamp() * 1000)
        except ValueError:
            self.logger.warning(
                f"Invalid last_run_timestamp: {last_run_iso}, defaulting to 0"
            )
            last_run_unix_sec = 0
            last_run_ms = 0

        # 2. Fetch messages from Gmail
        self.logger.info(
            "Fetching new messages from Gmail...", extra={"phase": "phase-2"}
        )
        query = f'-label:"{self.label_name}" after:{last_run_unix_sec}'
        messages = await self.gmail_client.fetch_messages(query)
        self.logger.info(
            f"Found {len(messages)} matching messages.",
            extra={"phase": "phase-2"},
        )

        if not messages:
            self.logger.info("No new messages to process.", extra={"phase": "setup"})
            return

        # 3. Fetch metadata for sorting and precise filtering
        self.logger.info("Fetching metadata for sorting...", extra={"phase": "phase-3"})
        try:
            metadata_tasks = [
                self.gmail_client.fetch_message_metadata(m["id"]) for m in messages
            ]
            messages_with_metadata = await asyncio.gather(*metadata_tasks)

            # Filter messages precisely by ms
            messages_with_metadata = [
                m
                for m in messages_with_metadata
                if int(m["internalDate"]) > last_run_ms
            ]

            # Sort oldest to newest
            messages_with_metadata.sort(key=lambda m: int(m["internalDate"]))
        except Exception:
            self.logger.exception(
                "Failed to fetch or sort message metadata",
                extra={"phase": "phase-3"},
            )
            return

        if not messages_with_metadata:
            self.logger.info(
                "No messages left after precise filtering.",
                extra={"phase": "setup"},
            )
            return

        # 4. Get label ID
        label_id = await self.gmail_client.get_or_create_label(self.label_name)

        # 5. Process messages
        self.logger.info("Processing messages...", extra={"phase": "phase-4"})
        results = await self.process_messages(messages_with_metadata, label_id)

        # 6. Update local state / watermark
        self.logger.info("Updating local state...", extra={"phase": "phase-6"})
        new_watermark = await self.state_manager.update_watermark(results)
        self.logger.info(f"New watermark: {new_watermark}", extra={"phase": "phase-6"})


async def setup_clients() -> (
    tuple[GmailClient, SheetsClient, LLMClient, StateManager] | None
):
    """Initialize all necessary clients using settings."""
    logger = logging.getLogger(__name__)
    try:
        gmail_service, sheets_service = await get_google_services_async(
            settings.GOOGLE_APPLICATION_CREDENTIALS
        )
        gmail_client = GmailClient(
            gmail_service, parallel_limit=settings.PARALLEL_LIMIT
        )
        sheets_client = SheetsClient(sheets_service)
        llm_client = LLMClient(
            api_url=settings.LLM_API_URL,
            model_name=settings.LLM_MODEL_NAME,
            parallel_limit=settings.PARALLEL_LIMIT,
            max_context=settings.LLM_MAX_CONTEXT,
            api_key=settings.LLM_API_KEY,
            user=settings.LLM_USER,
            password=settings.LLM_PASS,
        )
        state_file = getattr(settings, "STATE_FILE", "state.json")
        state_manager = StateManager(
            state_file, default_lookback_days=settings.DEFAULT_LOOKBACK_DAYS
        )
        logger.info("Clients initialized successfully.", extra={"phase": "setup"})
        return gmail_client, sheets_client, llm_client, state_manager
    except Exception:
        logger.exception("Failed to initialize clients", extra={"phase": "setup"})
        return None


async def main() -> None:
    """Main entry point."""
    clients_setup = await setup_clients()
    if not clients_setup:
        return
    gmail_client, sheets_client, llm_client, state_manager = clients_setup

    pipeline = Pipeline(
        gmail_client=gmail_client,
        sheets_client=sheets_client,
        llm_client=llm_client,
        state_manager=state_manager,
        label_name=settings.GMAIL_LABEL_NAME,
    )

    try:
        await pipeline.run()
    finally:
        await llm_client.close()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    asyncio.run(main())
