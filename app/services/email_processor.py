"""
Email Processor Service
طبقة خدمة بين الـ Scheduler والـ Orchestrator.
مسؤول عن:
  - جلب المستخدمين الفاعلين
  - تشغيل دورة المعالجة لكل مستخدم
  - تسجيل الأخطاء دون إيقاف الحلقة
"""
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.user import User
from app.agents.orchestrator import EmailOrchestrator

logger = logging.getLogger(__name__)


async def run_email_processing_cycle(db: AsyncSession) -> dict:
    """
    نقطة الدخول الرئيسية للمعالجة الدورية.
    يُعيد إحصائيات الدورة للـ logging.
    """
    result = await db.execute(
        select(User).where(
            User.is_active == True,
            User.gmail_connected == True,
        )
    )
    active_users = result.scalars().all()

    stats = {
        "users_processed": 0,
        "users_failed": 0,
        "total_emails_processed": 0,
    }

    if not active_users:
        logger.info("No active users found — skipping cycle.")
        return stats

    logger.info(f"Processing emails for {len(active_users)} active user(s).")
    orchestrator = EmailOrchestrator(db)

    for user in active_users:
        try:
            await orchestrator._process_user_emails(user)
            stats["users_processed"] += 1
        except Exception as e:
            logger.error(
                f"Failed processing user {user.id} "
                f"({user.gmail_address}): {e}",
                exc_info=True,
            )
            stats["users_failed"] += 1

    logger.info(
        f"Cycle done — "
        f"OK: {stats['users_processed']}, "
        f"Failed: {stats['users_failed']}"
    )
    return stats