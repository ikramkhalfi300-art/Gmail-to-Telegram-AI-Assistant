from sqlalchemy import Column, String, Text, DateTime, Integer, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base


class Draft(Base):
    __tablename__ = "drafts"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # ─── Multi-Tenant ─────────────────────────────────
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    email_id = Column(String, ForeignKey("emails.id"), index=True)

    # ─── Content ──────────────────────────────────────
    original_reply_text = Column(Text)          # النص الخام من تليجرام
    detected_language = Column(String)          # لغة رد المستخدم (dz/ar/fr/en)
    # اللغة التي كُتب بها الرد المقترح (= لغة المرسل الأصلي)
    reply_language = Column(String)
    composed_email = Column(Text)               # الرد المهني النهائي

    # ─── Approval Flow ────────────────────────────────
    # pending → approved | rejected | edited
    approved = Column(String, default="pending")
    sent_at = Column(DateTime)
    created_at = Column(DateTime, server_default=func.now())

    # ─── Telegram Tracking ────────────────────────────
    # message_id لرسالة طلب الموافقة في تليجرام (للتعديل لاحقاً)
    telegram_approval_message_id = Column(Integer, nullable=True)

    # ─── Relations ────────────────────────────────────
    user = relationship("User", back_populates="drafts")
    email = relationship("Email", back_populates="drafts")