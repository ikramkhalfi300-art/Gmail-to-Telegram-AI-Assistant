"""
اختبارات Telegram Webhook Router
يُختبر منطق التوجيه والتحقق من الأصالة
"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient
from httpx import AsyncClient, ASGITransport


# ─── Fixtures مشتركة ────────────────────────────────────
VALID_SECRET = "test-secret-token"
VALID_CHAT_ID = "111222333"

MOCK_USER = MagicMock()
MOCK_USER.id = 1
MOCK_USER.telegram_chat_id = VALID_CHAT_ID
MOCK_USER.is_active = True
MOCK_USER.gmail_connected = True
MOCK_USER.preferred_language = "ar"
MOCK_USER.gmail_token_json = '{"token":"fake"}'


def _text_update(text: str, chat_id: str = VALID_CHAT_ID) -> dict:
    return {
        "update_id": 1001,
        "message": {
            "message_id": 55,
            "chat": {"id": int(chat_id)},
            "from": {"id": int(chat_id), "username": "testuser"},
            "text": text,
        }
    }


def _callback_update(data: str, chat_id: str = VALID_CHAT_ID) -> dict:
    return {
        "update_id": 1002,
        "callback_query": {
            "id": "cq_123",
            "from": {"id": int(chat_id)},
            "data": data,
            "message": {
                "message_id": 44,
                "text": "مسودة الرد",
                "chat": {"id": int(chat_id)},
            }
        }
    }


# ─── Tests ──────────────────────────────────────────────
class TestTelegramWebhook:

    @pytest.fixture
    def app(self):
        from app.main import app
        return app

    async def test_rejects_invalid_secret(self, app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            response = await ac.post(
                "/webhooks/telegram",
                json=_text_update("مرحبا"),
                headers={"X-Telegram-Bot-Api-Secret-Token": "WRONG_SECRET"},
            )
        assert response.status_code == 403

    @patch("app.routers.webhooks._get_user_by_chat_id", new_callable=AsyncMock)
    @patch("app.routers.webhooks.EmailOrchestrator")
    async def test_start_command_registers_new_user(
        self, MockOrchestrator, mock_get_user, app
    ):
        mock_get_user.return_value = None  # مستخدم جديد
        mock_orchestrator = MagicMock()
        mock_orchestrator.telegram = MagicMock()
        mock_orchestrator.telegram.send_message = AsyncMock()
        MockOrchestrator.return_value = mock_orchestrator

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            response = await ac.post(
                "/webhooks/telegram",
                json=_text_update("/start"),
                headers={"X-Telegram-Bot-Api-Secret-Token": VALID_SECRET},
            )

        assert response.status_code == 200
        mock_orchestrator.telegram.send_message.assert_called_once()

    @patch("app.routers.webhooks._get_user_by_chat_id", new_callable=AsyncMock)
    @patch("app.routers.webhooks.EmailOrchestrator")
    async def test_text_message_routes_to_handle_text(
        self, MockOrchestrator, mock_get_user, app
    ):
        mock_get_user.return_value = MOCK_USER
        mock_orchestrator = MagicMock()
        mock_orchestrator.handle_text_message = AsyncMock()
        MockOrchestrator.return_value = mock_orchestrator

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            response = await ac.post(
                "/webhooks/telegram",
                json=_text_update("قله شكراً على التعاون"),
                headers={"X-Telegram-Bot-Api-Secret-Token": VALID_SECRET},
            )

        assert response.status_code == 200
        mock_orchestrator.handle_text_message.assert_called_once_with(
            user=MOCK_USER,
            message_text="قله شكراً على التعاون",
            message_id=55,
        )

    @patch("app.routers.webhooks._get_user_by_chat_id", new_callable=AsyncMock)
    @patch("app.routers.webhooks.EmailOrchestrator")
    async def test_callback_query_routes_to_handle_callback(
        self, MockOrchestrator, mock_get_user, app
    ):
        mock_get_user.return_value = MOCK_USER
        mock_orchestrator = MagicMock()
        mock_orchestrator.handle_callback_query = AsyncMock()
        MockOrchestrator.return_value = mock_orchestrator

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            response = await ac.post(
                "/webhooks/telegram",
                json=_callback_update("approve:42"),
                headers={"X-Telegram-Bot-Api-Secret-Token": VALID_SECRET},
            )

        assert response.status_code == 200
        mock_orchestrator.handle_callback_query.assert_called_once()
        call_kwargs = mock_orchestrator.handle_callback_query.call_args[1]
        assert call_kwargs["callback_data"] == "approve:42"

    @patch("app.routers.webhooks._get_user_by_chat_id", new_callable=AsyncMock)
    @patch("app.routers.webhooks.EmailOrchestrator")
    async def test_unknown_user_gets_error_message(
        self, MockOrchestrator, mock_get_user, app
    ):
        mock_get_user.return_value = None  # مستخدم غير مسجل (ليس /start)
        mock_orchestrator = MagicMock()
        mock_orchestrator.telegram = MagicMock()
        mock_orchestrator.telegram.send_message = AsyncMock()
        MockOrchestrator.return_value = mock_orchestrator

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            response = await ac.post(
                "/webhooks/telegram",
                json=_text_update("مرحبا"),
                headers={"X-Telegram-Bot-Api-Secret-Token": VALID_SECRET},
            )

        assert response.status_code == 200
        mock_orchestrator.telegram.send_message.assert_called_once()
        msg_text = mock_orchestrator.telegram.send_message.call_args[0][1]
        assert "/start" in msg_text

    async def test_empty_text_ignored(self, app):
        """الرسائل الفارغة أو الوسائط تُتجاهل بصمت."""
        update = {
            "update_id": 9999,
            "message": {
                "message_id": 1,
                "chat": {"id": 111},
                "from": {"id": 111},
                # لا يوجد "text"
                "photo": [{"file_id": "xyz"}],
            }
        }
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            response = await ac.post(
                "/webhooks/telegram",
                json=update,
                headers={"X-Telegram-Bot-Api-Secret-Token": VALID_SECRET},
            )
        assert response.status_code == 200
        assert response.json() == {"ok": True}