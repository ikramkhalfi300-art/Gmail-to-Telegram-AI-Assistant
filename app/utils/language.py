"""
مساعد كشف اللغة — يُستخدم في كل أنحاء التطبيق
طبقة مساعدة فوق langdetect + خريطة اللغات
"""
from langdetect import detect, LangDetectException

LANGUAGE_NAMES: dict[str, str] = {
    "en": "English", "ar": "Arabic", "fr": "French",
    "es": "Spanish", "de": "German", "it": "Italian",
    "pt": "Portuguese", "nl": "Dutch", "tr": "Turkish",
    "ru": "Russian", "zh": "Chinese", "ja": "Japanese",
    "ko": "Korean", "unknown": "Unknown",
}

LANGUAGE_CODES: dict[str, str] = {v: k for k, v in LANGUAGE_NAMES.items()}

# كلمات دارجة جزائرية شائعة — إذا وُجدت نعامل النص كعربية
DARIJA_KEYWORDS = {
    "واه", "لا باس", "مزيان", "بصح", "كيفاش", "وين",
    "هاك", "برك", "دابا", "بغيت", "ماشي", "راني",
    "chokran", "wach", "bghit", "mazal", "baraka",
}


def quick_detect(text: str) -> dict:
    """
    كشف سريع بدون API — يُستخدم كـ fallback.
    يُعيد: {"language_code": "fr", "language_name": "French"}
    """
    # فحص الدارجة الجزائرية أولاً
    lower = text.lower()
    darija_hits = sum(1 for word in DARIJA_KEYWORDS if word in lower)
    if darija_hits >= 2:
        return {
            "language_code": "ar",
            "language_name": "Arabic (Algerian Darija)",
            "confidence": "medium",
        }

    try:
        code = detect(text[:500])
        return {
            "language_code": code,
            "language_name": LANGUAGE_NAMES.get(code, f"Unknown ({code})"),
            "confidence": "medium",
        }
    except LangDetectException:
        return {
            "language_code": "unknown",
            "language_name": "Unknown",
            "confidence": "low",
        }


def get_language_name(code: str) -> str:
    return LANGUAGE_NAMES.get(code, f"Unknown ({code})")


def get_language_code(name: str) -> str:
    return LANGUAGE_CODES.get(name, "unknown")