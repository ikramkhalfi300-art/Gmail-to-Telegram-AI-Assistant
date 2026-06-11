import logging
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import select
from app.database import AsyncSessionLocal
from app.models.user import User
from app.config import get_settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])
settings = get_settings()


@router.get("/gmail")
async def gmail_auth(chat_id: str, request: Request):
    """
    بما أن الـ token موجود كـ Environment Variable على Railway،
    نحتاج فقط نربط المستخدم بحسابه ونفعّله.
    """
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(User).where(User.telegram_chat_id == chat_id)
        )
        user = result.scalar_one_or_none()

        if not user:
            return HTMLResponse("<h2>❌ المستخدم غير موجود. أرسل /start أولاً.</h2>")

        # تفعيل المستخدم
        user.is_active = True
        user.gmail_connected = True
        await db.commit()

        logger.info(f"User {chat_id} activated successfully")

    return HTMLResponse("""
        <html>
        <body style="font-family: Arial; text-align: center; padding: 50px;">
            <h1>✅ تم ربط Gmail بنجاح!</h1>
            <p>ارجع إلى Telegram وستبدأ في استقبال ملخصات إيميلاتك.</p>
        </body>
        </html>
    """)