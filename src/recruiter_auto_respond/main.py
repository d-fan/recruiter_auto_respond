import asyncio
import logging


async def main() -> None:
    """Main orchestrator for the AI Recruiter Labeler & Syncer."""
    logging.info("Starting the pipeline...")
    # 1. Load configuration and state
    # 2. Fetch messages from Gmail
    # 3. Classify with LLM
    # 4. Update Gmail labels
    # 5. Sync results to Google Sheets
    # 6. Update local state
    logging.info("Pipeline complete.")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    asyncio.run(main())
