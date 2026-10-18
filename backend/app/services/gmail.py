import base64
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from bs4 import BeautifulSoup
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
            flow = InstalledAppFlow.from_client_secrets_file(
                str(CREDENTIALS_PATH), SCOPES
            )
            creds = flow.run_local_server(port=0)
        TOKEN_PATH.write_text(creds.to_json())

    return build("gmail", "v1", credentials=creds)


def list_message_ids(service, query: str, max_results: int | None = None) -> list[str]:
    ids: list[str] = []
    page_token = None
    while True:
        response = (
            service.users()
            .messages()
            .list(userId="me", q=query, pageToken=page_token)
            .execute()
        )

        ids.extend(m["id"] for m in response.get("messages", []))

        if max_results is not None and len(ids) >= max_results:
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
    body: str


def get_message(service, msg_id: str) -> EmailData:
    msg = (
        service.users().messages().get(userId="me", id=msg_id, format="full").execute()
    )

    headers = {h["name"]: h["value"] for h in msg["payload"]["headers"]}
    received_at = int(msg["internalDate"]) / 1000

    return EmailData(
        gmail_id=msg["id"],
        thread_id=msg["threadId"],
        sender=headers.get("From", ""),
        subject=headers.get("Subject", ""),
        date=datetime.fromtimestamp(received_at, tz=UTC),
        body=_extract_body(msg["payload"]),
    )


def _html_to_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["style", "script"]):
        tag.decompose()
    return soup.get_text(separator="\n", strip=True)


def _extract_body(payload: dict) -> str:
    plain, html = [], []

    def walk(part: dict):
        data = part.get("body", {}).get("data")
        if data:
            raw = base64.urlsafe_b64decode(data)
            text = raw.decode("utf-8", errors="replace")
            if part.get("mimeType") == "text/plain":
                plain.append(text)
            if part.get("mimeType") == "text/html":
                html.append(text)

        for sub in part.get("parts", []):
            walk(sub)

    walk(payload)
    return "\n".join(plain) if plain else _html_to_text("\n".join(html))
