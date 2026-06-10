"""
Reply Handler Service
يُنظّم معالجة ردود المستخدم القادمة من تليجرام.
يُفصل منطق الرد عن الـ Orchestrator للحفاظ على مبدأ Single Responsibility.
"""

import logging 
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.user import User
from app.models.email import Email
from app.models.draft import Draft
from app.agents.composer import compose_reply, edit_draft
from app.integrations.telegram_client import TelegramClient
from app.integrations.gmail_client import GmailClient
from datetime import datetime

logger = logging.getLogger(__name__)


class ReplyHandler:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.telegram = TelegramClient()

    async def compose_and_send_draft(
        self,
        user: User,
        user_reply_text: str,
        user_language: str,
    ) -> Draft | None:
        """
        يُحضر آخر إيميل غير مُرَد عليه للمستخدم،
        يُصوغ رداً مهنياً بلغة المرسل،
        يُرسل طلب الموافقة لتليجرام.
        """
        # ─── جلب الإيميل المستهدف ─────────────────────
        result = await self.db.execute(
            select(Email)
            .where(
                Email.user_id == user.id,
                Email.status == "summarized",
            )
            .order_by(Email.received_at.desc())
            .limit(1)
        )
        email_obj = result.scalar_one_or_none()

        if not email_obj:
            await self.telegram.send_message(
                user.telegram_chat_id,
                "❌ لا يوجد إيميل في انتظار الرد حالياً.",
            )
            return None

        # ─── مؤشر الانتظار ────────────────────────────
        waiting_id = await self.telegram.send_waiting_indicator(user.telegram_chat_id)

        # ─── توليد الرد بلغة المرسل ───────────────────
        try:
            composed_text = await compose_reply(
                original_email={
                    "from_address": email_obj.from_address,
                    "subject":      email_obj.subject,
                    "body_clean":   email_obj.body_clean,
                },
                user_reply=user_reply_text,
                user_reply_language=user_language,
                sender_language_name=email_obj.detected_language,
                sender_language_code=email_obj.language_code,
            )
        except Exception as e:
            logger.error(f"compose_reply failed: {e}", exc_info=True)
            await self.telegram.send_error(user.telegram_chat_id, f"فشل توليد الرد: {e}")
            return None

        # ─── حفظ المسودة ──────────────────────────────
        draft = Draft(
            user_id=user.id,
            email_id=email_obj.id,
            original_reply_text=user_reply_text,
            detected_language=user_language,
            reply_language=email_obj.detected_language,
            composed_email=composed_text,
            approved="pending",
        )
        self.db.add(draft)
        await self.db.flush()  # نحتاج draft.id للأزرار

        # ─── إرسال طلب الموافقة ───────────────────────
        approval_msg_id = await self.telegram.send_draft_approval(
            chat_id=user.telegram_chat_id,
            draft_text=composed_text,
            draft_id=draft.id,
            reply_language=email_obj.detected_language,
            original_subject=email_obj.subject,
        )
        draft.telegram_approval_message_id = approval_msg_id

        await self.db.commit()

        # حذف مؤشر الانتظار
        if waiting_id:
            await self.telegram.edit_message_text(
                user.telegram_chat_id, waiting_id,
                "✅ _تمت صياغة الرد — راجع المسودة أدناه_",
                remove_keyboard=True,
            )

        return draft

    async def apply_edit(
        self,
        user: User,
        draft: Draft,
        edit_instruction: str,
        user_language: str,
    ) -> Draft | None:
        """يُعدّل مسودة قائمة ويُرسل النسخة المحدّثة للموافقة."""
        waiting_id = await self.telegram.send_waiting_indicator(user.telegram_chat_id)

        try:
            revised_text = await edit_draft(
                current_draft=draft.composed_email,
                edit_instruction=edit_instruction,
                user_edit_language=user_language,
                reply_language_name=draft.reply_language,
                reply_language_code="",
            )
        except Exception as e:
            logger.error(f"edit_draft failed: {e}", exc_info=True)
            await self.telegram.send_error(user.telegram_chat_id, f"فشل التعديل: {e}")
            return None

        draft.composed_email = revised_text

        email_obj = await self.db.get(Email, draft.email_id)
        new_msg_id = await self.telegram.send_draft_approval(
            chat_id=user.telegram_chat_id,
            draft_text=revised_text,
            draft_id=draft.id,
            reply_language=draft.reply_language,
            original_subject=email_obj.subject if email_obj else "—",
        )
        draft.telegram_approval_message_id = new_msg_id
        await self.db.commit()

        if waiting_id:
            await self.telegram.edit_message_text(
                user.telegram_chat_id, waiting_id,
                "✅ _تم تعديل المسودة_",
                remove_keyboard=True,
            )
        return draft

    async def send_approved_email(
        self,
        user: User,
        draft: Draft,
        message_id: int,
    ) -> bool:
        """يُرسل الإيميل عبر Gmail بعد الموافقة."""
        email_obj = await self.db.get(Email, draft.email_id)
        if not email_obj:
            await self.telegram.send_error(user.telegram_chat_id, "الإيميل الأصلي غير موجود.")
            return False

        try:
            gmail = GmailClient(token_json=user.gmail_token_json)
            gmail.send_reply(
                to=email_obj.from_address,
                subject=email_obj.subject,
                body=draft.composed_email,
                thread_id=email_obj.thread_id,
            )
            draft.approved = "approved"
            draft.sent_at = datetime.utcnow()
            email_obj.status = "replied"
            await self.db.commit()

            await self.telegram.edit_message_text(
                chat_id=user.telegram_chat_id,
                message_id=message_id,
                new_text=(
                    f"✅ *تم الإرسال بنجاح*\n"
                    f"إلى: `{email_obj.from_address}`\n"
                    f"الموضوع: {email_obj.subject}"
                ),
                remove_keyboard=True,
            )
            return True

        except Exception as e:
            logger.error(f"Gmail send failed for draft {draft.id}: {e}", exc_info=True)
            await self.telegram.send_error(user.telegram_chat_id, str(e))
            return False