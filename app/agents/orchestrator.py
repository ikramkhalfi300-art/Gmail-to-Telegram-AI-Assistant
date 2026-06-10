"""
Orchestrator المحدّث:
  - يعمل على كل مستخدمين الـ Multi-Tenant
  - يستخدم Telegram بدلاً من WhatsApp
  - يمرر لغة المرسل إلى الـ Composer
  - يتعامل مع CallbackQuery و رسائل نصية بشكل منفصل
"""
import logging
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.user import User
from app.models.email import Email
from app.models.draft import Draft
from app.models.conversation import Conversation
from app.agents.summarizer import summarize_email
from app.agents.composer import compose_reply, edit_draft
from app.agents.intent_router import parse_callback_query, detect_message_intent
from app.integrations.gmail_client import GmailClient
from app.integrations.telegram_client import TelegramClient
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class EmailOrchestrator:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.telegram = TelegramClient()

    def _get_gmail_client(self, user: User) -> GmailClient:
        """ينشئ Gmail client لمستخدم محدد باستخدام token الخاص به."""
        if not user.gmail_token_json:
            raise ValueError(f"User {user.id} has no Gmail token")
        return GmailClient(token_json=user.gmail_token_json)

    # ═══════════════════════════════════════════════════
    # STEP 1: دورة Polling — يمر على كل المستخدمين الفاعلين
    # ═══════════════════════════════════════════════════
    async def process_all_users_emails(self):
        """
        نقطة الدخول للـ Scheduler.
        يجلب كل المستخدمين الفاعلين المرتبطين بـ Gmail
        ويعالج إيميلاتهم في حلقة تكرارية.
        """
        result = await self.db.execute(
            select(User).where(
                User.is_active == True,
                User.gmail_connected == True
            )
        )
        active_users = result.scalars().all()

        logger.info(f"⏰ Polling emails for {len(active_users)} active user(s)...")

        for user in active_users:
            try:
                await self._process_user_emails(user)
            except Exception as e:
                logger.error(f"Error processing emails for user {user.id}: {e}")
                # لا نوقف الحلقة — نكمل باقي المستخدمين

    async def _process_user_emails(self, user: User):
        """يعالج إيميلات مستخدم واحد."""
        try:
            gmail = self._get_gmail_client(user)
        except ValueError as e:
            logger.warning(str(e))
            return

        emails = gmail.get_unread_emails(settings.max_emails_per_poll)
        logger.info(f"User {user.id} ({user.gmail_address}): {len(emails)} new email(s)")

        for email_data in emails:
            await self._process_single_email(email_data, user)

    async def _process_single_email(self, email_data: dict, user: User):
        """يعالج إيميلاً واحداً: يحفظه، يلخصه، ويرسل إشعاراً لتليجرام."""
        # تجنب معالجة نفس الإيميل مرتين
        existing = await self.db.get(Email, email_data["id"])
        if existing:
            return

        # ─── تلخيص الإيميل + كشف اللغة ──────────────
        summary_text, lang_info = await summarize_email(
            email_data,
            user_preferred_language=user.preferred_language
        )

        # ─── حفظ في قاعدة البيانات ───────────────────
        email_obj = Email(
            **email_data,
            user_id=user.id,
            status="pending",
            summary=summary_text,
            detected_language=lang_info["language_name"],
            language_code=lang_info["language_code"],
        )
        self.db.add(email_obj)
        await self.db.flush()  # للحصول على الـ ID

        # ─── إرسال إشعار تليجرام ─────────────────────
        try:
            tg_msg_id = await self.telegram.send_email_summary(
                chat_id=user.telegram_chat_id,
                summary=summary_text,
                email_id=email_data["id"],
                sender_language=lang_info["language_name"],
            )
            email_obj.telegram_message_id = tg_msg_id
            email_obj.status = "summarized"

            # قراءة الإيميل في Gmail
            gmail = self._get_gmail_client(user)
            gmail.mark_as_read(email_data["id"])

        except Exception as e:
            logger.error(f"Failed to send Telegram notification for email {email_data['id']}: {e}")

        await self.db.commit()

    # ═══════════════════════════════════════════════════
    # STEP 2: معالجة الـ CallbackQuery (أزرار Inline)
    # ═══════════════════════════════════════════════════
    async def handle_callback_query(
        self,
        user: User,
        callback_query_id: str,
        callback_data: str,
        message_id: int,
        text_body: str,
    ):
        """
        يُعالج ضغطات الأزرار (Inline Keyboard).
        callback_data أمثلة: "approve:42" | "reject:42" | "edit:42" | "start_reply:abc123"
        """
        parsed = parse_callback_query(callback_data)
        intent = parsed["intent"]
        draft_id = parsed.get("draft_id")

        # إيقاف loading spinner فوراً
        await self.telegram.answer_callback_query(callback_query_id)

        if intent == "APPROVE_DRAFT":
            await self._approve_draft(user, draft_id, message_id)

        elif intent == "REJECT_DRAFT":
            await self._reject_draft(user, draft_id, message_id)

        elif intent == "EDIT_DRAFT":
            # نطلب من المستخدم كتابة التعديل كرسالة نصية
            await self.telegram.edit_message_text(
                chat_id=user.telegram_chat_id,
                message_id=message_id,
                new_text=(
                    f"✍️ *تعديل المسودة #{draft_id}*\n\n"
                    f"اكتب التعديل الذي تريده كرسالة نصية وسأقوم بتطبيقه."
                ),
                remove_keyboard=True,
            )

        elif callback_data.startswith("start_reply:"):
            # زر "رد على هذا الإيميل" — يطلب من المستخدم كتابة الرد
            email_short_id = callback_data.split(":")[1]
            await self.telegram.send_message(
                chat_id=user.telegram_chat_id,
                text=(
                    "✍️ اكتب ردك بأي لغة تفضل (عربية، دارجة، فرنسية، إنجليزية...).\n"
                    "سأقوم بصياغة الرد المهني تلقائياً بنفس لغة المرسل. 🌐"
                )
            )

        # حفظ سجل التفاعل
        convo = Conversation(
            user_id=user.id,
            update_type="callback_query",
            callback_data=callback_data,
            body=text_body,
            direction="inbound",
            intent=intent,
            related_draft_id=draft_id,
        )
        self.db.add(convo)
        await self.db.commit()

    # ═══════════════════════════════════════════════════
    # STEP 3: معالجة الرسائل النصية العادية
    # ═══════════════════════════════════════════════════
    async def handle_text_message(
        self,
        user: User,
        message_text: str,
        message_id: int,
    ):
        """يُعالج الرسائل النصية (ليس الـ CallbackQuery)."""
        intent_data = await detect_message_intent(message_text)
        intent = intent_data["intent"]
        user_language = intent_data.get("language", "unknown")

        convo = Conversation(
            user_id=user.id,
            update_type="message",
            telegram_message_id=message_id,
            body=message_text,
            direction="inbound",
            intent=intent,
        )

        if intent == "REPLY_TO_EMAIL":
            await self._compose_reply_for_user(user, message_text, user_language, convo)

        elif intent == "REQUEST_SUMMARY":
            await self._send_pending_summaries(user)

        else:
            # UNKNOWN — ربما يحاول تعديل مسودة
            # نفحص إذا كان هناك مسودة معلقة
            pending_draft = await self._get_pending_draft(user)
            if pending_draft:
                await self._apply_edit_to_draft(user, pending_draft, message_text, user_language)
            else:
                await self.telegram.send_message(
                    chat_id=user.telegram_chat_id,
                    text=(
                        "❓ لم أفهم طلبك.\n\n"
                        "• أرسل ردك على الإيميل كرسالة نصية\n"
                        "• أو اضغط زر *موافقة* أو *إلغاء* على المسودة"
                    )
                )

        self.db.add(convo)
        await self.db.commit()

    # ─────────────────────────────────────────────
    # الدوال الداخلية
    # ─────────────────────────────────────────────
    async def _compose_reply_for_user(
        self,
        user: User,
        user_reply: str,
        user_reply_language: str,
        convo: Conversation,
    ):
        """يوجد آخر إيميل غير مُرَد عليه ويصوغ رداً بلغة المرسل."""
        # أرسل مؤشر انتظار
        waiting_msg_id = await self.telegram.send_waiting_indicator(user.telegram_chat_id)

        # أحضر آخر إيميل في انتظار الرد
        result = await self.db.execute(
            select(Email)
            .where(Email.user_id == user.id, Email.status == "summarized")
            .order_by(Email.received_at.desc())
            .limit(1)
        )
        email_obj = result.scalar_one_or_none()

        if not email_obj:
            await self.telegram.send_message(
                user.telegram_chat_id,
                "❌ لا يوجد إيميل في انتظار الرد حالياً."
            )
            return

        # ─── تصوية الرد بلغة المرسل ──────────────────
        composed = await compose_reply(
            original_email={
                "from_address": email_obj.from_address,
                "subject": email_obj.subject,
                "body_clean": email_obj.body_clean,
            },
            user_reply=user_reply,
            user_reply_language=user_reply_language,
            sender_language_name=email_obj.detected_language,
            sender_language_code=email_obj.language_code,
        )

        # ─── حفظ المسودة ─────────────────────────────
        draft = Draft(
            user_id=user.id,
            email_id=email_obj.id,
            original_reply_text=user_reply,
            detected_language=user_reply_language,
            reply_language=email_obj.detected_language,
            composed_email=composed,
            approved="pending",
        )
        self.db.add(draft)
        await self.db.flush()

        # ─── إرسال طلب الموافقة ───────────────────────
        approval_msg_id = await self.telegram.send_draft_approval(
            chat_id=user.telegram_chat_id,
            draft_text=composed,
            draft_id=draft.id,
            reply_language=email_obj.detected_language,
            original_subject=email_obj.subject,
        )
        draft.telegram_approval_message_id = approval_msg_id

        convo.related_email_id = email_obj.id
        convo.related_draft_id = draft.id

        # حذف رسالة الانتظار
        if waiting_msg_id:
            await self.telegram.edit_message_text(
                user.telegram_chat_id, waiting_msg_id,
                "✅ _تمت صياغة الرد — انظر أدناه_",
                remove_keyboard=True
            )

    async def _approve_draft(self, user: User, draft_id: int, message_id: int):
        """يُوافق على المسودة ويرسل الإيميل عبر Gmail."""
        draft = await self.db.get(Draft, draft_id)
        if not draft or draft.user_id != user.id:
            await self.telegram.send_error(user.telegram_chat_id, "المسودة غير موجودة.")
            return

        email_obj = await self.db.get(Email, draft.email_id)
        try:
            gmail = self._get_gmail_client(user)
            gmail.send_reply(
                to=email_obj.from_address,
                subject=email_obj.subject,
                body=draft.composed_email,
                thread_id=email_obj.thread_id
            )
            draft.approved = "approved"
            draft.sent_at = datetime.utcnow()
            email_obj.status = "replied"

            await self.telegram.edit_message_text(
                chat_id=user.telegram_chat_id,
                message_id=message_id,
                new_text=f"✅ *تم الإرسال بنجاح*\nإلى: `{email_obj.from_address}`",
                remove_keyboard=True,
            )
        except Exception as e:
            logger.error(f"Failed to send email for draft {draft_id}: {e}")
            await self.telegram.send_error(user.telegram_chat_id, str(e))

        await self.db.commit()

    async def _reject_draft(self, user: User, draft_id: int, message_id: int):
        """يرفض المسودة ويحذفها."""
        draft = await self.db.get(Draft, draft_id)
        if draft and draft.user_id == user.id:
            draft.approved = "rejected"
            await self.db.commit()

        await self.telegram.edit_message_text(
            chat_id=user.telegram_chat_id,
            message_id=message_id,
            new_text=f"🗑️ *تم حذف المسودة #{draft_id}*",
            remove_keyboard=True,
        )

    async def _apply_edit_to_draft(
        self,
        user: User,
        draft: Draft,
        edit_instruction: str,
        user_language: str,
    ):
        """يُطبق تعديل نصي على مسودة معلقة."""
        waiting_id = await self.telegram.send_waiting_indicator(user.telegram_chat_id)

        revised = await edit_draft(
            current_draft=draft.composed_email,
            edit_instruction=edit_instruction,
            user_edit_language=user_language,
            reply_language_name=draft.reply_language,
            reply_language_code="",  # سنضيف language_code للـ Draft في الإصدار التالي
        )
        draft.composed_email = revised

        email_obj = await self.db.get(Email, draft.email_id)
        new_msg_id = await self.telegram.send_draft_approval(
            chat_id=user.telegram_chat_id,
            draft_text=revised,
            draft_id=draft.id,
            reply_language=draft.reply_language,
            original_subject=email_obj.subject if email_obj else "—",
        )
        draft.telegram_approval_message_id = new_msg_id

        if waiting_id:
            await self.telegram.edit_message_text(
                user.telegram_chat_id, waiting_id,
                "✅ _تم تعديل المسودة — انظر أدناه_",
                remove_keyboard=True,
            )
        await self.db.commit()

    async def _get_pending_draft(self, user: User) -> Draft | None:
        """يُحضر آخر مسودة معلقة للمستخدم."""
        result = await self.db.execute(
            select(Draft)
            .where(Draft.user_id == user.id, Draft.approved == "pending")
            .order_by(Draft.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def _send_pending_summaries(self, user: User):
        """يُرسل ملخصات الإيميلات غير المُرَد عليها."""
        result = await self.db.execute(
            select(Email)
            .where(Email.user_id == user.id, Email.status == "summarized")
            .order_by(Email.received_at.desc())
            .limit(5)
        )
        emails = result.scalars().all()

        if not emails:
            await self.telegram.send_message(
                user.telegram_chat_id,
                "📭 لا توجد إيميلات في انتظار الرد."
            )
            return

        for email_obj in emails:
            await self.telegram.send_email_summary(
                chat_id=user.telegram_chat_id,
                summary=email_obj.summary or f"📧 {email_obj.subject}",
                email_id=email_obj.id,
                sender_language=email_obj.detected_language,
            )