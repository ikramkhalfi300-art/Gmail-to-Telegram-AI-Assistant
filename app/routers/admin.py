from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models.email import Email
from app.models.draft import Draft
from app.models.conversation import Conversation

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/emails")
async def list_emails(limit: int = 20, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Email).order_by(Email.received_at.desc()).limit(limit)
    )
    emails = result.scalars().all()
    return [
        {
            "id": e.id,
            "from": e.from_address,
            "subject": e.subject,
            "status": e.status,
            "received_at": str(e.received_at),
        }
        for e in emails
    ]


@router.get("/drafts")
async def list_drafts(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Draft).order_by(Draft.created_at.desc()).limit(20)
    )
    drafts = result.scalars().all()
    return [
        {
            "id": d.id,
            "email_id": d.email_id,
            "status": d.approved,
            "language": d.detected_language,
            "composed_preview": (d.composed_email or "")[:200],
            "created_at": str(d.created_at),
        }
        for d in drafts
    ]


@router.get("/conversations")
async def list_conversations(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Conversation).order_by(Conversation.created_at.desc()).limit(50)
    )
    convos = result.scalars().all()
    return [
        {
            "id": c.id,
            "direction": c.direction,
            "intent": c.intent,
            "body_preview": c.body[:100],
            "created_at": str(c.created_at),
        }
        for c in convos
    ]


@router.post("/poll-now")
async def trigger_poll(db: AsyncSession = Depends(get_db)):
    from app.agents.orchestrator import EmailOrchestrator
    orchestrator = EmailOrchestrator(db)
    await orchestrator.process_new_emails()
    return {"status": "poll triggered"}