"""
سكريبت اختبار يدوي لـ Telegram Bot — شغّله مرة واحدة للتأكد من الاتصال.
استخدام: python scripts/test_telegram.py
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from dotenv import load_dotenv
load_dotenv()

from app.integrations.telegram_client import TelegramClient


async def run_tests():
    client = TelegramClient()
    chat_id = input("أدخل chat_id الخاص بك (افتح @userinfobot في تيليجرام): ").strip()

    print("\n🔹 اختبار 1: إرسال رسالة بسيطة...")
    msg_id = await client.send_message(chat_id, "✅ *اختبار الاتصال* — البوت يعمل بشكل صحيح!")
    print(f"   ✅ message_id = {msg_id}")

    print("\n🔹 اختبار 2: إرسال ملخص إيميل مع زر...")
    summary = (
        "📧 *من:* client@example.com\n"
        "📌 *الموضوع:* طلب عرض أسعار\n"
        "🌐 *لغة المرسل:* French\n"
        "📝 *الملخص:* العميل يطلب عرض أسعار للخدمات الاستشارية.\n"
        "⚡ *الأولوية:* عالية\n"
        "🎯 *إجراء مطلوب:* نعم — إرسال عرض الأسعار"
    )
    sum_msg_id = await client.send_email_summary(
        chat_id=chat_id,
        summary=summary,
        email_id="testemail12345678",
        sender_language="French",
    )
    print(f"   ✅ summary message_id = {sum_msg_id}")

    print("\n🔹 اختبار 3: إرسال طلب موافقة على مسودة...")
    draft_text = (
        "Monsieur,\n\n"
        "Suite à votre demande, veuillez trouver ci-joint notre offre de prix "
        "pour les services de conseil.\n\n"
        "Nous restons à votre disposition pour tout renseignement complémentaire.\n\n"
        "Cordialement,\n[Votre Nom]"
    )
    approval_id = await client.send_draft_approval(
        chat_id=chat_id,
        draft_text=draft_text,
        draft_id=99,
        reply_language="French",
        original_subject="Demande de devis",
    )
    print(f"   ✅ approval message_id = {approval_id}")
    print("\n   ↑ جرّب الضغط على الأزرار للتأكد من عملها.")

    print("\n🔹 اختبار 4: ضبط Webhook...")
    from app.config import get_settings
    settings = get_settings()
    webhook_url = f"{settings.base_url}/webhooks/telegram"
    result = await client.set_webhook(webhook_url)
    print(f"   {'✅' if result else '❌'} Webhook set to: {webhook_url}")

    print("\n✅ جميع الاختبارات اكتملت!")


if __name__ == "__main__":
    asyncio.run(run_tests())