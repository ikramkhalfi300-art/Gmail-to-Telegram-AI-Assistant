from sqlalchemy import Column, String, Text, DateTime, Integer, ForeignKey
from sqlalchemy.sql import func
from app.database import Base


class Conversation(Base):
    """سجل كل تفاعل مع البوت (رسائل واردة + callback queries)."""
    __tablename__ = "conversations"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # ─── Multi-Tenant ─────────────────────────────────
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    # ─── Telegram Data ────────────────────────────────
    telegram_update_id = Column(String, unique=True, nullable=True)
    telegram_message_id = Column(Integer, nullable=True)
    # "message" | "callback_query"
    update_type = Column(String, default="message")
    # بيانات الـ callback (approve:{draft_id} | reject:{draft_id} | edit:{draft_id})
    callback_data = Column(String, nullable=True)

    body = Column(Text)
    direction = Column(String)   # inbound | outbound
    intent = Column(String)      # REPLY_TO_EMAIL | APPROVE_DRAFT | REJECT_DRAFT | EDIT_DRAFT | UNKNOWN

    related_email_id = Column(String, nullable=True)
    related_draft_id = Column(Integer, nullable=True)

    created_at = Column(DateTime, server_default=func.now())