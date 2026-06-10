import json
import logging
import anthropic
from langdetect import detect, LangDetectException

from app.config import get_settings
from app.utils.prompts import SUMMARIZE_EMAIL_PROMPT, DETECT_EMAIL_LANGUAGE_PROMPT

logger = logging.getLogger(__name__)
settings = get_settings()
client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

# خريطة ISO 639-1 → اسم اللغة
LANGUAGE_NAMES: dict[str, str] = {
    "en": "English",
    "ar": "Arabic",
    "fr": "French",
    "es": "Spanish",
    "de": "German",
    "it": "Italian",
    "pt": "Portuguese",
    "nl": "Dutch",
    "tr": "Turkish",
    "zh": "Chinese",
    "ja": "Japanese",
    "ko": "Korean",
    "ru": "Russian",
    "unknown": "Unknown",
}


async def detect_email_language(text: str) -> dict:
    """
    يكشف لغة النص بطبقتين:
    1. langdetect (سريع، بدون API call)
    2. Claude (للتحقق من حالات الدارجة الجزائرية والمحتوى المختلط)

    يُعيد: {"language_name": "French", "language_code": "fr", "confidence": "high"}
    """
    # ─── الطبقة الأولى: langdetect (fast path) ───────
    langdetect_code = "unknown"
    try:
        langdetect_code = detect(text[:500])
    except LangDetectException:
        pass

    # ─── الطبقة الثانية: Claude (للتحقق الدقيق) ─────
    try:
        prompt = DETECT_EMAIL_LANGUAGE_PROMPT.format(text=text[:1000])
        response = client.messages.create(
            model=settings.claude_model,
            max_tokens=150,
            messages=[{"role": "user", "content": prompt}]
        )
        raw = response.content[0].text.strip()
        # تنظيف أي markdown محتمل
        raw = raw.replace("```json", "").replace("```", "").strip()
        result = json.loads(raw)

        # تحقق من صحة الحقول
        language_code = result.get("language_code", langdetect_code or "unknown")
        language_name = result.get(
            "language_name",
            LANGUAGE_NAMES.get(language_code, "Unknown")
        )
        return {
            "language_name": language_name,
            "language_code": language_code,
            "confidence": result.get("confidence", "medium"),
        }

    except (json.JSONDecodeError, Exception) as e:
        logger.warning(f"Claude language detection failed, using langdetect fallback: {e}")
        code = langdetect_code or "unknown"
        return {
            "language_name": LANGUAGE_NAMES.get(code, "Unknown"),
            "language_code": code,
            "confidence": "low",
        }


async def summarize_email(email: dict, user_preferred_language: str = "ar") -> tuple[str, dict]:
    """
    يُلخص الإيميل وينتج ملخصاً لتليجرام.

    يُعيد:
        (summary_text, language_info)
        حيث language_info = {"language_name": ..., "language_code": ..., "confidence": ...}
    """
    # ─── كشف لغة المرسل ───────────────────────────────
    lang_info = await detect_email_language(email.get("body_clean", ""))
    logger.info(
        f"Email {email['id']}: detected language = "
        f"{lang_info['language_name']} ({lang_info['language_code']}), "
        f"confidence = {lang_info['confidence']}"
    )

    # ─── توليد الملخص ─────────────────────────────────
    prompt = SUMMARIZE_EMAIL_PROMPT.format(
        from_address=email["from_address"],
        subject=email["subject"],
        detected_language=lang_info["language_name"],
        language_code=lang_info["language_code"],
        body=email["body_clean"],
        user_preferred_language=user_preferred_language,
    )

    try:
        response = client.messages.create(
            model=settings.claude_model,
            max_tokens=700,
            messages=[{"role": "user", "content": prompt}]
        )
        summary = response.content[0].text
    except Exception as e:
        logger.error(f"Summarization failed for email {email['id']}: {e}")
        summary = (
            f"📧 *من:* {email['from_address']}\n"
            f"📌 *الموضوع:* {email['subject']}\n"
            f"📝 *الملخص:* [فشل توليد الملخص]\n"
            f"🌐 *لغة المرسل:* {lang_info['language_name']}"
        )

    return summary, lang_info