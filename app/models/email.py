from sqlalchemy import Column, String, Text, DateTime, Boolean, Integer, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base


class Email(Base):
    __tablename__ = "emails"

    id = Column(String, primary_key=True)           # Gmail message ID
    thread_id = Column(String, index=True)

    # ─── Multi-Tenant ─────────────────────────────────
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    # ─── Email Metadata ───────────────────────────────
    from_address = Column(String)
    to_address = Column(String)
    subject = Column(Text)
    body_raw = Column(Text)
    body_clean = Column(Text)
    summary = Column(Text)

    # ─── Language Detection (ميزة الرد بنفس اللغة) ───
    # اللغة المكتشفة من جسم الإيميل الوارد
    # القيم المحتملة: "arabic" | "french" | "english" | "spanish" | "unknown"
    detected_language = Column(String, default="unknown")
    # كود ISO 639-1 للغة (ar / fr / en / es / ...)
    language_code = Column(String, default="en")

    # ─── Timestamps & Status ──────────────────────────
    received_at = Column(DateTime)
    processed_at = Column(DateTime, server_default=func.now())
    # pending → summarized → replied | ignored
    status = Column(String, default="pending")

    # ─── Telegram Tracking ────────────────────────────
    telegram_message_id = Column(Integer, nullable=True)  # معرف رسالة التليجرام

    labels = Column(String)

    # ─── Relations ────────────────────────────────────
    user = relationship("User", back_populates="emails")
    drafts = relationship("Draft", back_populates="email", lazy="selectin")