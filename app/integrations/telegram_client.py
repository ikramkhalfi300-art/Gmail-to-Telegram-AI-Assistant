"""
Telegram Bot Client
يتعامل مع:
  - إرسال الرسائل النصية
  - إرسال الملخصات مع Inline Keyboards
  - إرسال طلبات الموافقة على المسودات
  - تعديل الرسائل الموجودة
  - إرسال التأكيدات والأخطاء
"""
import logging
import httpx
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

TELEGRAM_API_BASE = f"https://api.telegram.org/bot{settings.telegram_bot_token}"


class TelegramClient:
    def __init__(self):
        self.base_url = TELEGRAM_API_BASE
        # لا يوجد chat_id ثابت — يمرر في كل دالة

    async def _post(self, method: str, payload: dict) -> dict:
        """طلب POST لـ Telegram API."""
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.post(
                f"{self.base_url}/{method}",
                json=payload
            )
            data = response.json()
            if not data.get("ok"):
                logger.error(f"Telegram API error ({method}): {data}")
            return data

    # ─────────────────────────────────────────────
    # إرسال ملخص الإيميل + زر الرد
    # ─────────────────────────────────────────────
    async def send_email_summary(
        self,
        chat_id: str,
        summary: str,
        email_id: str,
        sender_language: str,
    ) -> int | None:
        """
        يرسل ملخص الإيميل مع زر واحد: ✍️ رد على هذا الإيميل.
        يُعيد message_id الرسالة المرسلة للتتبع.
        """
        payload = {
            "chat_id": chat_id,
            "text": summary,
            "parse_mode": "Markdown",
            "reply_markup": {
                "inline_keyboard": [[
                    {
                        "text": "✍️ رد على هذا الإيميل",
                        # نحفظ email_id للربط لاحقاً عند استقبال الرد النصي
                        "callback_data": f"start_reply:{email_id[:16]}"
                    }
                ]]
            }
        }
        result = await self._post("sendMessage", payload)
        if result.get("ok"):
            return result["result"]["message_id"]
        return None

    # ─────────────────────────────────────────────
    # إرسال طلب الموافقة على المسودة
    # ─────────────────────────────────────────────
    async def send_draft_approval(
        self,
        chat_id: str,
        draft_text: str,
        draft_id: int,
        reply_language: str,
        original_subject: str,
    ) -> int | None:
        """
        يرسل المسودة مع 3 أزرار تفاعلية:
          [🟢 موافقة وإرسال]  [✍️ تعديل الرد]  [🔴 إلغاء]
        """
        header = (
            f"✍️ *مسودة الرد — #{draft_id}*\n"
            f"📌 الموضوع: {original_subject}\n"
            f"🌐 لغة الرد: *{reply_language}*\n"
            f"{'─' * 30}\n\n"
        )
        message_body = f"{header}{draft_text}"

        # تجنب تجاوز حد تليجرام (4096 حرف)
        if len(message_body) > 4000:
            message_body = message_body[:3950] + "\n\n_... [تم اقتطاع النص]_"

        payload = {
            "chat_id": chat_id,
            "text": message_body,
            "parse_mode": "Markdown",
            "reply_markup": {
                "inline_keyboard": [
                    [
                        {
                            "text": "🟢 موافقة وإرسال",
                            "callback_data": f"approve:{draft_id}"
                        },
                        {
                            "text": "✍️ تعديل الرد",
                            "callback_data": f"edit:{draft_id}"
                        },
                    ],
                    [
                        {
                            "text": "🔴 إلغاء وحذف",
                            "callback_data": f"reject:{draft_id}"
                        }
                    ]
                ]
            }
        }
        result = await self._post("sendMessage", payload)
        if result.get("ok"):
            return result["result"]["message_id"]
        return None

    # ─────────────────────────────────────────────
    # تعديل رسالة موجودة (بعد الموافقة أو الرفض)
    # ─────────────────────────────────────────────
    async def edit_message_text(
        self,
        chat_id: str,
        message_id: int,
        new_text: str,
        remove_keyboard: bool = True,
    ) -> bool:
        """يُعدّل نص رسالة موجودة ويحذف الأزرار اختيارياً."""
        payload = {
            "chat_id": chat_id,
            "message_id": message_id,
            "text": new_text,
            "parse_mode": "Markdown",
        }
        if remove_keyboard:
            payload["reply_markup"] = {"inline_keyboard": []}

        result = await self._post("editMessageText", payload)
        return result.get("ok", False)

    # ─────────────────────────────────────────────
    # Answer Callback Query (لإخفاء loading spinner)
    # ─────────────────────────────────────────────
    async def answer_callback_query(
        self,
        callback_query_id: str,
        text: str = "",
        show_alert: bool = False,
    ) -> bool:
        """يُرسل إجابة لـ CallbackQuery لإيقاف الـ loading spinner."""
        payload = {
            "callback_query_id": callback_query_id,
            "text": text,
            "show_alert": show_alert,
        }
        result = await self._post("answerCallbackQuery", payload)
        return result.get("ok", False)

    # ─────────────────────────────────────────────
    # رسائل النظام
    # ─────────────────────────────────────────────
    async def send_message(self, chat_id: str, text: str) -> int | None:
        """رسالة نصية بسيطة بدون أزرار."""
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "Markdown",
        }
        result = await self._post("sendMessage", payload)
        if result.get("ok"):
            return result["result"]["message_id"]
        return None

    async def send_success(self, chat_id: str, to_address: str) -> None:
        await self.send_message(
            chat_id,
            f"✅ *تم الإرسال بنجاح*\nأُرسل الإيميل إلى: `{to_address}`"
        )

    async def send_error(self, chat_id: str, error: str) -> None:
        await self.send_message(
            chat_id,
            f"❌ *حدث خطأ:*\n`{error}`"
        )

    async def send_waiting_indicator(self, chat_id: str) -> int | None:
        """يرسل رسالة انتظار أثناء توليد المسودة."""
        return await self.send_message(
            chat_id,
            "⏳ _جاري صياغة الرد المهني..._"
        )

    # ─────────────────────────────────────────────
    # ضبط Webhook
    # ─────────────────────────────────────────────
    async def set_webhook(self, webhook_url: str) -> bool:
        payload = {
            "url": webhook_url,
            "secret_token": settings.telegram_webhook_secret,
            "allowed_updates": ["message", "callback_query"],
            "drop_pending_updates": True,
        }
        result = await self._post("setWebhook", payload)
        if result.get("ok"):
            logger.info(f"✅ Telegram webhook set to: {webhook_url}")
        return result.get("ok", False)

    async def delete_webhook(self) -> bool:
        result = await self._post("deleteWebhook", {"drop_pending_updates": True})
        return result.get("ok", False)