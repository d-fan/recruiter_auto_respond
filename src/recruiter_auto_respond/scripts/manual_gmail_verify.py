import asyncio
import json
import logging
import sys
from typing import Any

from recruiter_auto_respond.config import settings
from recruiter_auto_respond.gmail_client import GmailClient
from recruiter_auto_respond.google_auth import get_google_services_async

# --- MANUAL VERIFICATION INPUTS ---
# Replace these values with your actual query/ID for verification.
SEARCH_QUERY = "YOUR_QUERY_HERE"
MESSAGE_ID = "YOUR_MSG_ID_HERE"
# -----------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)


def pretty_print_json(data: Any) -> None:
    """Pretty-print a dictionary or list as JSON."""
    print(json.dumps(data, indent=2))


async def verify_gmail_operations() -> None:
    """Manual verification script for GmailClient operations."""
    logger.info("Starting manual Gmail verification...")

    # 1. Initialize Gmail Service
    try:
        gmail_service, _ = await get_google_services_async(
            settings.GOOGLE_APPLICATION_CREDENTIALS
        )
        gmail_client = GmailClient(gmail_service)
        logger.info("Gmail service initialized successfully.")
    except Exception:
        logger.exception("Failed to initialize Gmail service")
        return

    # 2. Verify: fetch_messages
    if SEARCH_QUERY and SEARCH_QUERY != "YOUR_QUERY_HERE":
        logger.info(f"Verifying fetch_messages with query: '{SEARCH_QUERY}'")
        try:
            messages = await gmail_client.fetch_messages(SEARCH_QUERY)
            logger.info(f"Found {len(messages)} messages.")
            if messages:
                logger.info("First 3 messages (IDs and Thread IDs):")
                pretty_print_json(messages[:3])
        except Exception:
            logger.exception("Error during fetch_messages")
    else:
        logger.warning("SEARCH_QUERY is not set. Skipping fetch_messages verification.")

    # 3. Verify: fetch_message_body
    if MESSAGE_ID and MESSAGE_ID != "YOUR_MSG_ID_HERE":
        logger.info(f"Verifying fetch_message_body for ID: {MESSAGE_ID}")
        try:
            body = await gmail_client.fetch_message_body(MESSAGE_ID)
            if body:
                logger.info("Message body successfully fetched:")
                print("-" * 40)
                print(body)
                print("-" * 40)
            else:
                logger.warning(f"No body found for message ID: {MESSAGE_ID}")
        except Exception:
            logger.exception("Error during fetch_message_body")
    else:
        logger.warning(
            "MESSAGE_ID is not set. Skipping fetch_message_body verification."
        )

    logger.info("Manual Gmail verification complete.")


if __name__ == "__main__":
    try:
        asyncio.run(verify_gmail_operations())
    except KeyboardInterrupt:
        logger.info("Verification script cancelled by user.")
