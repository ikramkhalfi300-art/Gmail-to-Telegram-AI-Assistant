"""
Telegram Webhook Router
يستقبل نوعين من الـ Updates:
  1. message: رسائل نصية عادية من المستخدم
  2. callback_query: ضغطات أزرار الـ Inline Keyboard
"""
import logging
from fastapi import APIRouter, Request, HTTPException, Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models.user import User
from app.agents.orchestrator import EmailOrchestrator
from app.config import get_settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/webhooks", tags=["webhooks"])
settings = get_settings()


async def _get_user_by_chat_id(chat_id: str, db: AsyncSession) -> User | None:
    """يُحضر المستخدم بناءً على telegram_chat_id."""
    result = await db.execute(
        select(User).where(User.telegram_chat_id == chat_id)
    )
    return result.scalar_one_or_none()


@router.post("/telegram")
async def telegram_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
    x_telegram_bot_api_secret_token: str = Header(default=""),
):
    """
    نقطة استقبال Telegram Webhook.
    تليجرام يُرسل كل Update هنا كـ POST request.
    """
    # ─── التحقق من الأصالة ────────────────────────
    if x_telegram_bot_api_secret_token != settings.telegram_webhook_secret:
        logger.warning("Invalid Telegram webhook secret token")
        raise HTTPException(status_code=403, detail="Forbidden")

    update = await request.json()
    logger.info(f"📲 Telegram update received: {list(update.keys())}")

    orchestrator = EmailOrchestrator(db)

    # ─── نوع 1: Callback Query (ضغطة زر) ──────────
    if "callback_query" in update:
        cq = update["callback_query"]
        chat_id = str(cq["from"]["id"])
        user = await _get_user_by_chat_id(chat_id, db)

        if not user:
            logger.warning(f"Unknown Telegram user: {chat_id}")
            return {"ok": True}

        await orchestrator.handle_callback_query(
            user=user,
            callback_query_id=cq["id"],
            callback_data=cq.get("data", ""),
            message_id=cq.get("message", {}).get("message_id"),
            text_body=cq.get("message", {}).get("text", ""),
        )

    # ─── نوع 2: رسالة نصية عادية ──────────────────
    elif "message" in update:
        msg = update["message"]
        chat_id = str(msg["chat"]["id"])
        text = msg.get("text", "").strip()

        if not text:
            return {"ok": True}  # تجاهل الوسائط والملفات

        user = await _get_user_by_chat_id(chat_id, db)

        # ─── تسجيل مستخدم جديد عبر /start ──────────
        if text.startswith("/start"):
            if not user:
                new_user = User(
                    telegram_chat_id=chat_id,
                    telegram_username=msg["from"].get("username"),
                    preferred_language="ar",
                    is_active=False,
                    gmail_connected=False,
                )
                db.add(new_user)
                await db.commit()
                logger.info(f"New user registered: {chat_id}")

            await orchestrator.telegram.send_message(
                chat_id=chat_id,
                text=(
                    "👋 *مرحباً في AI Email Assistant!*\n\n"
                    "🔗 لربط حساب Gmail الخاص بك، قم بزيارة:\n"
                    f"`{settings.base_url}/auth/gmail?chat_id={chat_id}`\n\n"
                    "بعد الربط ستبدأ في استقبال ملخصات إيميلاتك هنا. 📧"
                )
            )
            return {"ok": True}

        if not user:
            await orchestrator.telegram.send_message(
                chat_id=chat_id,
                text="❌ حسابك غير مسجل. أرسل /start للبدء."
            )
            return {"ok": True}

        await orchestrator.handle_text_message(
            user=user,
            message_text=text,
            message_id=msg["message_id"],
        )

    return {"ok": True}