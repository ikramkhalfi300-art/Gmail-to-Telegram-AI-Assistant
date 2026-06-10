import json
import logging
import anthropic

from app.config import get_settings
from app.utils.prompts import INTENT_DETECTION_PROMPT

logger = logging.getLogger(__name__)
settings = get_settings()
client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

VALID_INTENTS = {"REPLY_TO_EMAIL", "REQUEST_SUMMARY", "UNKNOWN"}


def parse_callback_query(callback_data: str) -> dict:
    """
    يُحلل بيانات الـ Inline Keyboard بدون Claude.
    صيغة الـ callback_data: "action:draft_id"
    أمثلة: "approve:42" | "reject:42" | "edit:42"
    
    يُعيد:
        {"intent": "APPROVE_DRAFT", "draft_id": 42}
    """
    ACTION_MAP = {
        "approve": "APPROVE_DRAFT",
        "reject":  "REJECT_DRAFT",
        "edit":    "EDIT_DRAFT",
    }
    try:
        parts = callback_data.split(":")
        action = parts[0].lower()
        draft_id = int(parts[1]) if len(parts) > 1 else None
        intent = ACTION_MAP.get(action, "UNKNOWN")
        return {"intent": intent, "draft_id": draft_id}
    except Exception as e:
        logger.error(f"Failed to parse callback_data '{callback_data}': {e}")
        return {"intent": "UNKNOWN", "draft_id": None}


async def detect_message_intent(message: str) -> dict:
    """
    يكشف نية الرسائل النصية العادية (ليس الـ CallbackQuery).
    
    يُعيد:
        {"intent": "REPLY_TO_EMAIL", "language": "arabic", "content": "..."}
    """
    # Fast path: طلبات الملخص الشائعة
    SUMMARY_TRIGGERS = {
        "ملخص", "ارسل ملخص", "شو عندي", "وين الإيميلات",
        "summary", "show emails", "mes emails", "résumé"
    }
    if message.strip().lower() in SUMMARY_TRIGGERS:
        return {"intent": "REQUEST_SUMMARY", "language": "mixed", "content": message}

    prompt = INTENT_DETECTION_PROMPT.format(message=message)
    try:
        response = client.messages.create(
            model=settings.claude_model,
            max_tokens=200,
            messages=[{"role": "user", "content": prompt}]
        )
        raw = response.content[0].text.strip()
        raw = raw.replace("```json", "").replace("```", "").strip()
        result = json.loads(raw)
        if result.get("intent") not in VALID_INTENTS:
            result["intent"] = "UNKNOWN"
        return result
    except Exception as e:
        logger.error(f"Intent detection failed: {e}")
        return {"intent": "UNKNOWN", "language": "unknown", "content": message}