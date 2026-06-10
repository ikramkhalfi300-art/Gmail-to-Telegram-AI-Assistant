import logging
import anthropic

from app.config import get_settings
from app.utils.prompts import COMPOSE_REPLY_PROMPT, EDIT_DRAFT_PROMPT

logger = logging.getLogger(__name__)
settings = get_settings()
client = anthropic.Anthropic(api_key=settings.anthropic_api_key)


async def compose_reply(
    original_email: dict,
    user_reply: str,
    user_reply_language: str,
    sender_language_name: str,
    sender_language_code: str,
) -> str:
    """
    يصوغ رداً مهنياً بنفس لغة المرسل الأصلي.

    Args:
        original_email: بيانات الإيميل الأصلي (from, subject, body_clean)
        user_reply: تعليمات المستخدم بأي لغة
        user_reply_language: اللغة التي كتب بها المستخدم تعليماته
        sender_language_name: اسم لغة المرسل الأصلي (e.g. "French")
        sender_language_code: كود ISO للغة (e.g. "fr")
    """
    prompt = COMPOSE_REPLY_PROMPT.format(
        from_address=original_email["from_address"],
        subject=original_email["subject"],
        sender_language_name=sender_language_name,
        sender_language_code=sender_language_code,
        original_body=original_email["body_clean"][:2500],
        user_reply=user_reply,
        user_reply_language=user_reply_language,
    )

    logger.info(
        f"Composing reply in {sender_language_name} ({sender_language_code}) "
        f"from user instruction in {user_reply_language}"
    )

    response = client.messages.create(
        model=settings.claude_model,
        max_tokens=1200,
        messages=[{"role": "user", "content": prompt}]
    )
    return response.content[0].text


async def edit_draft(
    current_draft: str,
    edit_instruction: str,
    user_edit_language: str,
    reply_language_name: str,
    reply_language_code: str,
) -> str:
    """
    يُعدّل مسودة موجودة مع الحفاظ على لغة المرسل الأصلي.
    """
    prompt = EDIT_DRAFT_PROMPT.format(
        current_draft=current_draft,
        reply_language_name=reply_language_name,
        reply_language_code=reply_language_code,
        edit_instruction=edit_instruction,
        user_edit_language=user_edit_language,
    )

    response = client.messages.create(
        model=settings.claude_model,
        max_tokens=1200,
        messages=[{"role": "user", "content": prompt}]
    )
    return response.content[0].text