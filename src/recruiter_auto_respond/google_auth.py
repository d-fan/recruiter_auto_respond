import asyncio
import logging
import os
from typing import Any

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# If modifying these scopes, delete the file token.json.
SCOPES = [
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/spreadsheets",
]


def get_google_services(
    credentials_path: str,
    token_path: str = "token.json",
) -> tuple[Any, Any]:
    """Authenticates with Google and returns Gmail and Sheets service objects."""
    creds = None
    # The file token.json stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)  # type: ignore[no-untyped-call]

    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            logging.info("Refreshing Google OAuth2 credentials...")
            creds.refresh(Request())
        else:
            logging.info("Initial Google OAuth2 flow required.")
            flow = InstalledAppFlow.from_client_secrets_file(credentials_path, SCOPES)
            creds = flow.run_local_server(port=0)

        # Save the credentials for the next run
        with open(token_path, "w", encoding="utf-8") as token:
            token.write(creds.to_json())

    gmail_service = build("gmail", "v1", credentials=creds)
    sheets_service = build("sheets", "v4", credentials=creds)

    return gmail_service, sheets_service


async def get_google_services_async(
    credentials_path: str,
    token_path: str = "token.json",
) -> tuple[Any, Any]:
    """Async wrapper for get_google_services."""
    return await asyncio.to_thread(get_google_services, credentials_path, token_path)
