"""
اختبارات وحدة للـ Agents (بدون API calls حقيقية — كل شيء مُحاكى)
"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock


# ══════════════════════════════════════════════
# Summarizer Tests
# ══════════════════════════════════════════════
class TestLanguageDetection:

    @patch("app.agents.summarizer.detect")
    @patch("app.agents.summarizer.client")
    async def test_detect_english_email(self, mock_client, mock_detect):
        from app.agents.summarizer import detect_email_language

        mock_detect.return_value = "en"
        mock_client.messages.create.return_value = MagicMock(
            content=[MagicMock(text='{"language_name":"English","language_code":"en","confidence":"high"}')]
        )

        result = await detect_email_language("Hello, please find attached the report.")
        assert result["language_code"] == "en"
        assert result["language_name"] == "English"

    @patch("app.agents.summarizer.detect")
    @patch("app.agents.summarizer.client")
    async def test_detect_french_email(self, mock_client, mock_detect):
        from app.agents.summarizer import detect_email_language

        mock_detect.return_value = "fr"
        mock_client.messages.create.return_value = MagicMock(
            content=[MagicMock(text='{"language_name":"French","language_code":"fr","confidence":"high"}')]
        )

        result = await detect_email_language("Bonjour, veuillez trouver ci-joint le rapport.")
        assert result["language_code"] == "fr"

    @patch("app.agents.summarizer.detect")
    @patch("app.agents.summarizer.client")
    async def test_fallback_on_claude_failure(self, mock_client, mock_detect):
        """إذا فشلت Claude، يُستخدم langdetect كـ fallback."""
        from app.agents.summarizer import detect_email_language

        mock_detect.return_value = "ar"
        mock_client.messages.create.side_effect = Exception("API error")

        result = await detect_email_language("مرحبا، أرجو الاطلاع على التقرير المرفق.")
        assert result["language_code"] == "ar"
        assert result["confidence"] == "low"


# ══════════════════════════════════════════════
# Composer Tests
# ══════════════════════════════════════════════
class TestComposer:

    @patch("app.agents.composer.client")
    async def test_compose_reply_in_sender_language(self, mock_client):
        """يجب أن يُصاغ الرد بلغة المرسل وليس المستخدم."""
        from app.agents.composer import compose_reply

        mock_client.messages.create.return_value = MagicMock(
            content=[MagicMock(text="Monsieur, Suite à votre email...")]
        )

        result = await compose_reply(
            original_email={
                "from_address": "client@paris.fr",
                "subject": "Demande de devis",
                "body_clean": "Bonjour, pouvez-vous m'envoyer un devis?",
            },
            user_reply="قله راه سنبعتلو الفاتورة غدوة",
            user_reply_language="darija",
            sender_language_name="French",
            sender_language_code="fr",
        )

        # التحقق أن الـ prompt يحتوي على إجبار اللغة الفرنسية
        call_args = mock_client.messages.create.call_args
        prompt_sent = call_args[1]["messages"][0]["content"]
        assert "French" in prompt_sent
        assert "MANDATORY" in prompt_sent or "fr" in prompt_sent
        assert result == "Monsieur, Suite à votre email..."

    @patch("app.agents.composer.client")
    async def test_edit_draft_preserves_language(self, mock_client):
        from app.agents.composer import edit_draft

        mock_client.messages.create.return_value = MagicMock(
            content=[MagicMock(text="Dear Sir, Please find the revised offer...")]
        )

        result = await edit_draft(
            current_draft="Dear Sir, Please find the offer attached.",
            edit_instruction="اجعله أكثر رسمية",
            user_edit_language="arabic",
            reply_language_name="English",
            reply_language_code="en",
        )
        assert "Dear Sir" in result


# ══════════════════════════════════════════════
# Intent Router Tests
# ══════════════════════════════════════════════
class TestIntentRouter:

    def test_parse_approve_callback(self):
        from app.agents.intent_router import parse_callback_query
        result = parse_callback_query("approve:42")
        assert result["intent"] == "APPROVE_DRAFT"
        assert result["draft_id"] == 42

    def test_parse_reject_callback(self):
        from app.agents.intent_router import parse_callback_query
        result = parse_callback_query("reject:7")
        assert result["intent"] == "REJECT_DRAFT"
        assert result["draft_id"] == 7

    def test_parse_edit_callback(self):
        from app.agents.intent_router import parse_callback_query
        result = parse_callback_query("edit:15")
        assert result["intent"] == "EDIT_DRAFT"
        assert result["draft_id"] == 15

    def test_parse_invalid_callback(self):
        from app.agents.intent_router import parse_callback_query
        result = parse_callback_query("garbage_data")
        assert result["intent"] == "UNKNOWN"
        assert result["draft_id"] is None

    @patch("app.agents.intent_router.client")
    async def test_detect_reply_intent(self, mock_client):
        from app.agents.intent_router import detect_message_intent

        mock_client.messages.create.return_value = MagicMock(
            content=[MagicMock(
                text='{"intent":"REPLY_TO_EMAIL","language":"arabic","content":"قله شكراً"}'
            )]
        )
        result = await detect_message_intent("قله شكراً على التعاون")
        assert result["intent"] == "REPLY_TO_EMAIL"
        assert result["language"] == "arabic"

    async def test_summary_trigger_fast_path(self):
        """الكلمات المفتاحية يجب أن تُكتشف بدون Claude."""
        from app.agents.intent_router import detect_message_intent
        result = await detect_message_intent("ملخص")
        assert result["intent"] == "REQUEST_SUMMARY"


# ══════════════════════════════════════════════
# Language Utils Tests
# ══════════════════════════════════════════════
class TestLanguageUtils:

    def test_get_language_name(self):
        from app.utils.language import get_language_name
        assert get_language_name("fr") == "French"
        assert get_language_name("ar") == "Arabic"
        assert get_language_name("xx") == "Unknown (xx)"

    def test_darija_detection(self):
        from app.utils.language import quick_detect
        result = quick_detect("واه مزيان، بغيت نعرف كيفاش")
        assert result["language_code"] == "ar"
        assert "Darija" in result["language_name"]

    @patch("app.utils.language.detect")
    def test_fallback_on_exception(self, mock_detect):
        from app.utils.language import quick_detect
        from langdetect import LangDetectException
        mock_detect.side_effect = LangDetectException(0, "error")
        result = quick_detect("???")
        assert result["language_code"] == "unknown"