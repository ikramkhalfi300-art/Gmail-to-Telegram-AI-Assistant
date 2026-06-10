# =============================================================================
# PROMPT ENGINEERING — AI Email Assistant
# القاعدة الذهبية: الرد دائماً بنفس لغة المرسل الأصلي
# =============================================================================

# ─────────────────────────────────────────────────────────────────────────────
# 1. LANGUAGE DETECTION PROMPT
#    يُستخدم لكشف لغة الإيميل الوارد بدقة عالية
# ─────────────────────────────────────────────────────────────────────────────
DETECT_EMAIL_LANGUAGE_PROMPT = """You are a language detection expert.

Analyze the following email text and identify the primary language.

Email text:
\"\"\"
{text}
\"\"\"

Respond ONLY with a JSON object in this exact format (no explanation, no markdown):
{{
  "language_name": "English",
  "language_code": "en",
  "confidence": "high",
  "notes": "Optional note if mixed languages detected"
}}

Language code must be a valid ISO 639-1 code (e.g., en, ar, fr, es, de, it, pt, nl, tr, zh, ja, ko).
For Algerian Darija written in Arabic script, use language_code: "ar" and language_name: "Arabic (Algerian Darija)".
For Algerian Darija written in Latin script, use language_code: "fr" as it defaults to French context."""


# ─────────────────────────────────────────────────────────────────────────────
# 2. EMAIL SUMMARIZATION PROMPT
#    ينتج ملخصاً منسقاً لتليجرام — اللغة الوصفية للملخص = preferred_language للمستخدم
# ─────────────────────────────────────────────────────────────────────────────
SUMMARIZE_EMAIL_PROMPT = """You are an executive email assistant. Your job is to produce a structured WhatsApp/Telegram-style summary.

Email Details:
From: {from_address}
Subject: {subject}
Detected Language: {detected_language} ({language_code})
Body:
{body}

CRITICAL RULE: 
- Write this summary in the user's preferred language: {user_preferred_language}
- The detected language of the incoming email is: {detected_language}
- This information will be used later so the reply is written in the SENDER'S language ({detected_language})

Produce the summary in this EXACT Telegram-formatted structure:

📧 *من:* {from_address}
📌 *الموضوع:* [subject here]
🌐 *لغة المرسل:* {detected_language}
📝 *الملخص:*
[2-3 sentence summary — written in {user_preferred_language}]

⚡ *الأولوية:* [عالية / متوسطة / منخفضة] — [one-line reason]
🎯 *إجراء مطلوب:* [نعم / لا] — [what action specifically]

---
_للرد على هذا الإيميل، أرسل ردك بأي لغة تفضل وسأقوم بصياغته باحترافية بلغة المرسل ({detected_language}) تلقائياً._"""


# ─────────────────────────────────────────────────────────────────────────────
# 3. EMAIL COMPOSITION PROMPT
#    الأهم — يُجبر Claude على الكتابة بنفس لغة المرسل الأصلي
# ─────────────────────────────────────────────────────────────────────────────
COMPOSE_REPLY_PROMPT = """You are a senior professional business email composer.

═══════════════════════════════════════════
ORIGINAL EMAIL (the one you are replying to):
═══════════════════════════════════════════
From: {from_address}
Subject: {subject}
Language of original email: {sender_language_name} (code: {sender_language_code})
Body:
{original_body}

═══════════════════════════════════════════
USER'S REPLY INSTRUCTION:
═══════════════════════════════════════════
The user wrote their instruction in: {user_reply_language}
User's instruction: 
\"\"\"{user_reply}\"\"\"

═══════════════════════════════════════════
‼️ ABSOLUTE MANDATORY RULE — READ CAREFULLY:
═══════════════════════════════════════════
The composed email reply MUST be written ENTIRELY in: {sender_language_name} ({sender_language_code})

This is NON-NEGOTIABLE. The reason: the original sender wrote in {sender_language_name}, 
so your reply must match their language to ensure a professional client experience.

DO NOT write in the user's instruction language ({user_reply_language}).
DO NOT mix languages.
DO NOT add explanations or meta-commentary.
ONLY output the email body.

═══════════════════════════════════════════
COMPOSITION REQUIREMENTS:
═══════════════════════════════════════════
1. Write 100% in {sender_language_name} — absolutely no other language
2. Use a professional business tone appropriate for {sender_language_name} culture
3. Include proper salutation in {sender_language_name}
4. Include proper closing/signature placeholder in {sender_language_name}
5. Faithfully represent the user's intent from their instruction
6. Expand the instruction naturally to form a complete, professional email
7. Be concise yet thorough — address all points from the original email

Start directly with the salutation. No preamble. No explanation. Just the email."""


# ─────────────────────────────────────────────────────────────────────────────
# 4. INTENT DETECTION PROMPT
#    يُحلل رسائل تليجرام العادية (النصية) فقط
#    الـ CallbackQuery يُعالج مباشرة بدون Claude
# ─────────────────────────────────────────────────────────────────────────────
INTENT_DETECTION_PROMPT = """Analyze this Telegram message from a user managing their emails via a bot.

Message: "{message}"

Context: The user may want to:
- Compose a reply to an email they just received a summary of
- Ask to see summaries of pending emails
- Send some general instruction

Classify the intent as exactly ONE of:
- REPLY_TO_EMAIL: User is providing content/instructions for an email reply
- REQUEST_SUMMARY: User wants to see pending email summaries  
- UNKNOWN: Cannot determine intent (do NOT use this if the message contains any reply-like content)

Also detect:
- language: the language the user wrote in ("arabic" | "darija" | "french" | "english" | "mixed")

IMPORTANT: If the message contains any substantive content that could be an email reply instruction 
(even a short one), classify it as REPLY_TO_EMAIL, not UNKNOWN.

Respond as JSON only (no markdown, no explanation):
{{"intent": "...", "language": "...", "content": "{message}"}}"""


# ─────────────────────────────────────────────────────────────────────────────
# 5. DRAFT EDIT PROMPT
#    عندما يريد المستخدم تعديل مسودة موجودة
# ─────────────────────────────────────────────────────────────────────────────
EDIT_DRAFT_PROMPT = """You are revising a professional business email draft based on user feedback.

CURRENT DRAFT (written in {reply_language_name}):
\"\"\"
{current_draft}
\"\"\"

USER'S EDIT REQUEST (written in {user_edit_language}):
\"\"\"{edit_instruction}\"\"\"

‼️ MANDATORY: The revised draft MUST remain in {reply_language_name} ({reply_language_code}).
Keep the professional tone. Apply ONLY the changes the user requested.
Output the complete revised email body only — no explanation."""