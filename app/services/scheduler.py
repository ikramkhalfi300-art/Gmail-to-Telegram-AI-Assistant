import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.database import AsyncSessionLocal
from app.agents.orchestrator import EmailOrchestrator
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()
scheduler = AsyncIOScheduler(timezone="UTC")


async def poll_all_users_emails_job():
    """
    Job الـ Scheduler — يُشغَّل كل N ثانية.
    يمر على كل المستخدمين الفاعلين في قاعدة البيانات.
    """
    logger.info("⏰ Starting email polling cycle for all active users...")
    async with AsyncSessionLocal() as db:
        orchestrator = EmailOrchestrator(db)
        try:
            await orchestrator.process_all_users_emails()
            logger.info("✅ Email polling cycle completed.")
        except Exception as e:
            logger.error(f"Critical error in polling job: {e}", exc_info=True)


def start_scheduler():
    scheduler.add_job(
        poll_all_users_emails_job,
        trigger="interval",
        seconds=settings.email_fetch_interval * 60,
        id="email_poller_all_users",
        replace_existing=True,
        max_instances=1,            # منع التشغيل المتزامن
        coalesce=True,              # تجاهل الـ jobs المتأخرة
    )
    scheduler.start()
    logger.info(
        f"✅ Scheduler started — polling every {settings.email_fetch_interval * 60}s"
    )


def stop_scheduler():
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped.")