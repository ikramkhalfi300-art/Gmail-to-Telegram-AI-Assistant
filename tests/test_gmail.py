"""
اختبارات Gmail Client — كل طلبات Google API مُحاكاة
"""
import pytest
import base64
from unittest.mock import MagicMock, patch


def _make_gmail_client(mock_service):
    """ينشئ GmailClient مع service مُحاكى بدون OAuth."""
    with patch("app.integrations.gmail_client.Credentials") as mock_creds_cls, \
         patch("app.integrations.gmail_client.os.path.exists", return_value=True), \
         patch("app.integrations.gmail_client.build", return_value=mock_service):

        mock_creds = MagicMock()
        mock_creds.valid = True
        mock_creds_cls.from_authorized_user_file.return_value = mock_creds

        from app.integrations.gmail_client import GmailClient
        client = GmailClient(token_json='{"token":"fake"}')
        client.service = mock_service
        return client


class TestGmailClient:

    def _build_mock_message(self, msg_id="msg123", subject="Test Subject",
                             from_addr="sender@example.com",
                             body_text="Hello world", lang="en"):
        """يبني رسالة Gmail مُحاكاة."""
        body_bytes = base64.urlsafe_b64encode(body_text.encode()).decode()
        return {
            "id": msg_id,
            "threadId": "thread123",
            "internalDate": "1700000000000",
            "labelIds": ["INBOX", "UNREAD"],
            "payload": {
                "headers": [
                    {"name": "From",    "value": from_addr},
                    {"name": "To",      "value": "me@example.com"},
                    {"name": "Subject", "value": subject},
                ],
                "mimeType": "text/plain",
                "body": {"data": body_bytes},
            }
        }

    def test_get_unread_emails_returns_list(self):
        mock_service = MagicMock()
        mock_service.users().messages().list().execute.return_value = {
            "messages": [{"id": "msg1"}, {"id": "msg2"}]
        }
        mock_msg = self._build_mock_message("msg1")
        mock_service.users().messages().get().execute.return_value = mock_msg

        client = _make_gmail_client(mock_service)
        emails = client.get_unread_emails(max_results=5)

        assert isinstance(emails, list)
        assert emails[0]["from_address"] == "sender@example.com"
        assert emails[0]["subject"] == "Test Subject"
        assert emails[0]["body_clean"] == "Hello world"

    def test_get_unread_emails_empty(self):
        mock_service = MagicMock()
        mock_service.users().messages().list().execute.return_value = {"messages": []}

        client = _make_gmail_client(mock_service)
        result = client.get_unread_emails()
        assert result == []

    def test_mark_as_read(self):
        mock_service = MagicMock()
        client = _make_gmail_client(mock_service)
        client.mark_as_read("msg123")

        mock_service.users().messages().modify.assert_called_once_with(
            userId="me",
            id="msg123",
            body={"removeLabelIds": ["UNREAD"]},
        )

    def test_send_reply(self):
        mock_service = MagicMock()
        mock_service.users().messages().send().execute.return_value = {"id": "sent_msg_id"}

        client = _make_gmail_client(mock_service)
        sent_id = client.send_reply(
            to="recipient@example.com",
            subject="Test",
            body="Hello there",
            thread_id="thread123",
        )
        assert sent_id == "sent_msg_id"
        mock_service.users().messages().send.assert_called()

    def test_clean_html_strips_tags(self):
        mock_service = MagicMock()
        client = _make_gmail_client(mock_service)
        result = client._clean_html("<p>Hello <b>World</b></p>")
        assert "<p>" not in result
        assert "Hello" in result
        assert "World" in result

    def test_body_truncated_to_4000_chars(self):
        """يجب أن يُقطَع نص الإيميل الطويل عند 4000 حرف."""
        mock_service = MagicMock()
        long_text = "x" * 10000
        body_b64 = base64.urlsafe_b64encode(long_text.encode()).decode()
        mock_msg = {
            "id": "msg1", "threadId": "t1",
            "internalDate": "1700000000000", "labelIds": [],
            "payload": {
                "headers": [
                    {"name": "From",    "value": "a@b.com"},
                    {"name": "To",      "value": "me@b.com"},
                    {"name": "Subject", "value": "Long email"},
                ],
                "mimeType": "text/plain",
                "body": {"data": body_b64},
            }
        }
        mock_service.users().messages().list().execute.return_value = {
            "messages": [{"id": "msg1"}]
        }
        mock_service.users().messages().get().execute.return_value = mock_msg

        client = _make_gmail_client(mock_service)
        emails = client.get_unread_emails()
        assert len(emails[0]["body_clean"]) <= 4000