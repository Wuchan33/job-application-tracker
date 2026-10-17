from pathlib import Path
from dataclasses import dataclass
from datetime import datetime
from email.utils import parsedate_to_datetime

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build


SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

BACKEND_DIR = Path(__file__).resolve().parents[2]
CREDENTIALS_PATH = BACKEND_DIR / "credentials.json"
TOKEN_PATH = BACKEND_DIR / "token.json"

def get_service():
    creds = None
    if TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_PATH), SCOPES)
            creds = flow.run_local_server(port=0)
        TOKEN_PATH.write_text(creds.to_json())

    return build("gmail", "v1", credentials=creds)

def list_message_ids(service, query: str, max_results: int ):
    ids: list[str] = []
    page_token = None
    while True:
        response = service.users().messages().list(
            userId = "me",
            q = query,
            pageToken = page_token
        ).execute()

        ids.extend(m["id"] for m in response.get("messages", []))

        if max_results and len(ids) >= max_results:
            return ids[:max_results]

        page_token = response.get("nextPageToken")
        if not page_token:
            return ids

@dataclass
class EmailData:
    gmail_id: str
    thread_id: str
    sender: str
    subject: str
    date: datetime

def get_message(service, msg_id: str) -> EmailData:
    msg = service.users().messages().get(
        userId = "me",
        id = msg_id,
        format = "full"
    ).execute()

    headers = {h["name"]: h["value"] for h in msg["payload"]["headers"]}

    return EmailData(
        gmail_id = msg["id"],
        thread_id = msg["threadId"],
        sender = headers.get("From", ""),
        subject = headers.get("Subject", ""),
        date = parsedate_to_datetime(headers["Date"])
    )

if __name__ == "__main__":
    service = get_service()
    for msg_id in list_message_ids(service, "newer_than:30d", max_results=3):
        print(get_message(service, msg_id))


