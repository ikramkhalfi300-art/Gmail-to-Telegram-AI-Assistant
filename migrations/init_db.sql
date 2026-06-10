-- ══════════════════════════════════════════════
-- Multi-Tenant AI Email Assistant — Database Schema
-- ══════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS users (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_chat_id      TEXT UNIQUE NOT NULL,
    telegram_username     TEXT,
    gmail_address         TEXT,
    -- token مخزن كـ JSON — يُشفَّر في الإنتاج
    gmail_token_json      TEXT,
    -- لغة التواصل المفضلة مع البوت: ar / fr / en
    preferred_language    TEXT DEFAULT 'ar',
    is_active             INTEGER DEFAULT 0,
    gmail_connected       INTEGER DEFAULT 0,
    created_at            DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_seen_at          DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS emails (
    id                    TEXT PRIMARY KEY,   -- Gmail message ID
    thread_id             TEXT,
    user_id               INTEGER NOT NULL REFERENCES users(id),
    from_address          TEXT,
    to_address            TEXT,
    subject               TEXT,
    body_raw              TEXT,
    body_clean            TEXT,
    summary               TEXT,
    -- حقول كشف اللغة (ميزة الرد بنفس اللغة)
    detected_language     TEXT DEFAULT 'unknown',  -- "French" / "Arabic" / ...
    language_code         TEXT DEFAULT 'en',       -- ISO 639-1: fr / ar / en / ...
    received_at           DATETIME,
    processed_at          DATETIME DEFAULT CURRENT_TIMESTAMP,
    -- pending → summarized → replied | ignored
    status                TEXT DEFAULT 'pending',
    telegram_message_id   INTEGER,
    labels                TEXT
);

CREATE TABLE IF NOT EXISTS drafts (
    id                          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id                     INTEGER NOT NULL REFERENCES users(id),
    email_id                    TEXT REFERENCES emails(id),
    original_reply_text         TEXT,       -- نص المستخدم الخام
    detected_language           TEXT,       -- لغة المستخدم (dz/ar/fr/en)
    reply_language              TEXT,       -- لغة الرد = لغة المرسل الأصلي
    composed_email              TEXT,       -- الرد المهني النهائي
    -- pending → approved | rejected | edited
    approved                    TEXT DEFAULT 'pending',
    sent_at                     DATETIME,
    created_at                  DATETIME DEFAULT CURRENT_TIMESTAMP,
    telegram_approval_message_id INTEGER
);

CREATE TABLE IF NOT EXISTS conversations (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id               INTEGER NOT NULL REFERENCES users(id),
    telegram_update_id    TEXT UNIQUE,
    telegram_message_id   INTEGER,
    -- "message" | "callback_query"
    update_type           TEXT DEFAULT 'message',
    callback_data         TEXT,
    body                  TEXT,
    -- "inbound" | "outbound"
    direction             TEXT,
    -- REPLY_TO_EMAIL | APPROVE_DRAFT | REJECT_DRAFT | EDIT_DRAFT | REQUEST_SUMMARY | UNKNOWN
    intent                TEXT,
    related_email_id      TEXT,
    related_draft_id      INTEGER,
    created_at            DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- ── Indexes ──────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_users_telegram    ON users(telegram_chat_id);
CREATE INDEX IF NOT EXISTS idx_users_active      ON users(is_active, gmail_connected);
CREATE INDEX IF NOT EXISTS idx_emails_user       ON emails(user_id, status);
CREATE INDEX IF NOT EXISTS idx_emails_status     ON emails(status);
CREATE INDEX IF NOT EXISTS idx_drafts_user       ON drafts(user_id, approved);
CREATE INDEX IF NOT EXISTS idx_convos_user       ON conversations(user_id, created_at);