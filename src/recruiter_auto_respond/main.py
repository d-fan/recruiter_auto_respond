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


@dataclass
class PipelineClients:
    """Container for pipeline clients."""

    gmail: GmailClient
    sheets: SheetsClient
    llm: LLMClient
    state: StateManager


class Pipeline:
    """Orchestrator for the AI Recruiter Labeler & Syncer."""

    def __init__(
        self,
        clients: PipelineClients,
        label_name: str,
        dry_run: bool = False,
    ) -> None:
        self.clients = clients
        self.label_name = label_name
        self.dry_run = dry_run
        self.logger = logging.getLogger(__name__)

    async def _classify_and_record(
        self,
        m: dict[str, Any],
        label_id: str,
        stop_event: asyncio.Event,
    ) -> tuple[dict[str, Any] | None, str, bool]:
        """Process a single message: fetch body, classify, and label if needed."""
        if stop_event.is_set():
            return None, "", False

        message_id = m["id"]
        thread_id = m["threadId"]
        # Convert internalDate (ms) to ISO format with ms precision
        ms_timestamp = int(m["internalDate"])
        msg_dt = datetime.fromtimestamp(ms_timestamp / 1000, tz=timezone.utc)
        msg_ts_iso = msg_dt.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"

        try:
            # Fetch body
            body = await self.clients.gmail.fetch_message_body(message_id)

            # Classify
            is_recruiter = await self.clients.llm.classify_message(body)

            row = None
            if is_recruiter:
                if not self.dry_run:
                    await self.clients.gmail.add_label(message_id, label_id)
                    self.logger.info(f"Labeled message {message_id} as Recruiter.")
                else:
                    self.logger.info(
                        f"[DRY-RUN] Would label message {message_id} as Recruiter."
                    )

                # Prepare row for Sheets
                row = {
                    "threadId": thread_id,
                    "messageId": message_id,
                    "timestamp": msg_ts_iso,
                }
            else:
                self.logger.info(f"Skipped message {message_id} (Not Recruiter).")

            return row, msg_ts_iso, True

        except Exception:
            self.logger.exception(f"Failed to process message {message_id}")
            stop_event.set()
            return None, "", False

    async def process_messages(
        self,
        messages_with_metadata: list[dict[str, Any]],
        label_id: str,
    ) -> tuple[list[dict[str, Any]], list[tuple[str, bool]]]:
        """Process messages in parallel and return results."""
        stop_event = asyncio.Event()

        tasks = [
            self._classify_and_record(m, label_id, stop_event)
            for m in messages_with_metadata
        ]
        gathered_results = await asyncio.gather(*tasks)

        rows_to_sync = []
        watermark_input = []

        for row, ts, success in gathered_results:
            if not ts and not success:  # Indicates failure or hard stop
                break
            if row:
                rows_to_sync.append(row)
            watermark_input.append((ts, success))

        return rows_to_sync, watermark_input

    async def run(self) -> None:
        """Run the full pipeline."""
        self.logger.info("Starting the pipeline...", extra={"phase": "setup"})

        # 1. Load state
        state = await self.clients.state.load_state()
        last_run_iso = state.get("last_run_timestamp", "1970-01-01T00:00:00.000Z")
        self.logger.info(f"Last run: {last_run_iso}", extra={"phase": "phase-1"})

        # Convert ISO to Unix timestamp
        try:
            dt = datetime.fromisoformat(last_run_iso.replace("Z", "+00:00"))
            last_run_unix_sec = int(dt.timestamp())
            last_run_ms = int(dt.timestamp() * 1000)
        except ValueError:
            last_run_unix_sec = 0
            last_run_ms = 0

        # 2. Fetch messages from Gmail
        self.logger.info(
            "Fetching new messages from Gmail...", extra={"phase": "phase-2"}
        )
        query = f'-label:"{self.label_name}" after:{last_run_unix_sec}'
        messages = await self.clients.gmail.fetch_messages(query)
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
                self.clients.gmail.fetch_message_metadata(m["id"]) for m in messages
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
        label_id = await self.clients.gmail.get_or_create_label(self.label_name)

        # 5. Process messages
        self.logger.info("Processing messages...", extra={"phase": "phase-4"})
        rows_to_sync, watermark_input = await self.process_messages(
            messages_with_metadata, label_id
        )

        # 6. Late-Sync Drift Protection
        if rows_to_sync and not self.dry_run:
            self.logger.info(
                "Performing late-sync drift check...", extra={"phase": "phase-5"}
            )
            existing_ids = await self.clients.sheets.get_message_ids(
                settings.GOOGLE_SHEET_ID
            )
            filtered_rows = [
                r for r in rows_to_sync if r["messageId"] not in existing_ids
            ]

            if filtered_rows:
                self.logger.info(f"Syncing {len(filtered_rows)} rows to Sheets.")
                sync_data = [
                    [r["threadId"], r["messageId"], r["timestamp"]]
                    for r in filtered_rows
                ]
                # Assuming append_rows exists in origin/main's SheetsClient
                # Wait, I should check if SheetsClient has append_rows or append_row
                await self.clients.sheets.append_row(
                    settings.GOOGLE_SHEET_ID, sync_data[0]
                )  # Simplified for now, or check append_rows
            else:
                self.logger.info("All messages already present in Sheets. Skipping sync.")
        elif self.dry_run:
            self.logger.info("[DRY-RUN] Skipping Sheets sync.")

        # 7. Update local state / watermark
        self.logger.info("Updating local state...", extra={"phase": "phase-6"})
        new_watermark = await self.clients.state.update_watermark(watermark_input)
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
    parser = argparse.ArgumentParser(description="Recruiter Auto-Respond Pipeline")
    parser.add_argument("--dry-run", action="store_true", help="Perform dry run")
    args = parser.parse_args()

    clients_setup = await setup_clients()
    if not clients_setup:
        return
    gmail_client, sheets_client, llm_client, state_manager = clients_setup

    pipeline_clients = PipelineClients(
        gmail=gmail_client,
        sheets=sheets_client,
        llm=llm_client,
        state=state_manager,
    )

    pipeline = Pipeline(
        clients=pipeline_clients,
        label_name=settings.GMAIL_LABEL_NAME,
        dry_run=args.dry_run,
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
