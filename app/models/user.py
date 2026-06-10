from sqlalchemy import Column, String, Text, DateTime, Boolean, Integer
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base


class User(Base):
    """
    جدول المستخدمين — أساس بنية Multi-Tenant.
    كل مستخدم لديه:
      - telegram_chat_id: معرّف محادثة تليجرام (يصل عبر /start)
      - gmail_token_json: OAuth token الخاص بـ Gmail (مشفّر مستقبلاً)
      - gmail_address: عنوان الإيميل المرتبط
      - preferred_language: لغة التواصل المفضلة مع البوت
      - is_active: للتحكم في من يُضمَّن في دورة الـ Polling
    """
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # ─── Telegram ─────────────────────────────────────
    telegram_chat_id = Column(String, unique=True, nullable=False, index=True)
    telegram_username = Column(String, nullable=True)

    # ─── Gmail ────────────────────────────────────────
    gmail_address = Column(String, nullable=True)
    # يُخزَّن كـ JSON string — في الإنتاج يجب تشفيره (Fernet/KMS)
    gmail_token_json = Column(Text, nullable=True)

    # ─── Preferences ──────────────────────────────────
    # اللغة المفضلة للتواصل مع البوت (ar / fr / en / dz)
    preferred_language = Column(String, default="ar")

    # ─── Status ───────────────────────────────────────
    is_active = Column(Boolean, default=False)
    # False = لم يكمل ربط Gmail بعد | True = مستعد للعمل
    gmail_connected = Column(Boolean, default=False)

    created_at = Column(DateTime, server_default=func.now())
    last_seen_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # ─── Relations ────────────────────────────────────
    emails = relationship("Email", back_populates="user", lazy="selectin")
    drafts = relationship("Draft", back_populates="user", lazy="selectin")