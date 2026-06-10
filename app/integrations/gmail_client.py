import base64
import json
import os
import tempfile
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List, Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from bs4 import BeautifulSoup

from app.config import get_settings

settings = get_settings()
SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]


class GmailClient:
    def __init__(self):
        self.service = None
        self._authenticate()

    def _authenticate(self):
        creds = None

        # محاولة القراءة من Environment Variable أولاً (Railway)
        token_json_str = os.environ.get("GMAIL_TOKEN_JSON")

        if token_json_str:
            token_data = json.loads(token_json_str)
            creds = Credentials.from_authorized_user_info(token_data, SCOPES)
        elif os.path.exists(settings.gmail_token_path):
            # fallback للتشغيل المحلي
            creds = Credentials.from_authorized_user_file(
                settings.gmail_token_path, SCOPES
            )

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
                # حفظ التوكن المحدث محلياً فقط
                if not token_json_str:
                    with open(settings.gmail_token_path, "w") as f:
                        f.write(creds.to_json())
            else:
                raise RuntimeError(
                    "Gmail credentials missing or expired. "
                    "Run scripts/setup_gmail_oauth.py first."
                )

        self.service = build("gmail", "v1", credentials=creds)

    def get_unread_emails(self, max_results: int = 10) -> List[dict]:
        results = self.service.users().messages().list(
            userId="me",
            q="is:unread -category:promotions -category:social",
            maxResults=max_results
        ).execute()

        messages = results.get("messages", [])
        emails = []
        for msg in messages:
            detail = self._get_email_detail(msg["id"])
            if detail:
                emails.append(detail)
        return emails

    def _get_email_detail(self, message_id: str) -> Optional[dict]:
        msg = self.service.users().messages().get(
            userId="me", id=message_id, format="full"
        ).execute()

        headers = {h["name"]: h["value"] for h in msg["payload"]["headers"]}
        body_raw = self._extract_body(msg["payload"])
        body_clean = self._clean_html(body_raw)

        received_ts = int(msg.get("internalDate", 0)) / 1000
        received_at = datetime.fromtimestamp(received_ts) if received_ts else datetime.utcnow()

        return {
            "id": message_id,
            "thread_id": msg.get("threadId"),
            "from_address": headers.get("From", ""),
            "to_address": headers.get("To", ""),
            "subject": headers.get("Subject", "(No Subject)"),
            "body_raw": body_raw,
            "body_clean": body_clean[:4000],
            "received_at": received_at,
            "labels": ",".join(msg.get("labelIds", [])),
        }

    def _extract_body(self, payload: dict) -> str:
        if "parts" in payload:
            for part in payload["parts"]:
                if part["mimeType"] == "text/plain":
                    data = part["body"].get("data", "")
                    return base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")
                elif part["mimeType"] == "text/html":
                    data = part["body"].get("data", "")
                    return base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")
        else:
            data = payload["body"].get("data", "")
            if data:
                return base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")
        return ""

    def _clean_html(self, html: str) -> str:
        if "<" in html and ">" in html:
         soup = BeautifulSoup(html, "lxml")
         return soup.get_text(separator="\n").strip()
        return html.strip()

    def mark_as_read(self, message_id: str):
        self.service.users().messages().modify(
            userId="me",
            id=message_id,
            body={"removeLabelIds": ["UNREAD"]}
        ).execute()

    def send_reply(self, to: str, subject: str, body: str, thread_id: str) -> str:
        msg = MIMEMultipart()
        msg["to"] = to
        msg["subject"] = f"Re: {subject}" if not subject.startswith("Re:") else subject
        msg.attach(MIMEText(body, "plain"))

        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
        sent = self.service.users().messages().send(
            userId="me",
            body={"raw": raw, "threadId": thread_id}
        ).execute()
        return sent["id"]