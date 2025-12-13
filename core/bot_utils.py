import requests
from django.conf import settings

# Webhook URL (o'zingizniki to'g'ri ekanligiga ishonch hosil qiling)
WEBHOOK_URL = "https://miniapp.tunl.uz/webhook/" 
# Tokenni settings.py dan olish maslahat beriladi, lekin hozircha shu yerda tursin
BOT_TOKEN = "5315308944:AAHAdfv2djwecCS7aiieLOyGbbtkfjNjAg8"
BASE_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"

def send_confirmation_request(telegram_id, debt_obj, domain):
    """
    Mijozga 'Tasdiqlash' tugmasi bilan xabar yuboradi.
    Tugma bosilganda Telegram Mini App ochiladi.
    """
    web_app_url = f"https://{domain}/debt/{debt_obj.uuid}/"
    
    # --- Multicurrency Logic ---
    sum_parts = []
    
    # Agar so'm qismi bo'lsa (0 dan katta bo'lsa)
    if debt_obj.amount_uzs and debt_obj.amount_uzs > 0:
        # 1,000,000 ko'rinishida formatlaymiz va vergulni probelga almashtiramiz
        uzs_fmt = f"{debt_obj.amount_uzs:,.0f}".replace(",", " ")
        sum_parts.append(f"{uzs_fmt} so'm")
        
    # Agar dollar qismi bo'lsa
    if debt_obj.amount_usd and debt_obj.amount_usd > 0:
        # $100.50 ko'rinishida
        usd_fmt = f"${debt_obj.amount_usd:,.2f}"
        sum_parts.append(usd_fmt)
        
    # Ikkalasini birlashtiramiz (Masalan: "500 000 so'm + $50")
    total_str = " + ".join(sum_parts) if sum_parts else "0 so'm"
    # ---------------------------

    text = (
        f"🆕 <b>Yangi Nasiya qaydi!</b>\n\n"
        f"🛒 <b>Tovarlar:</b>\n{debt_obj.items}\n\n"
        f"💰 <b>Jami:</b> {total_str}\n\n"
        f"Iltimos, pastdagi tugmani bosib tasdiqlang yoki rad eting."
    )

    payload = {
        "chat_id": telegram_id,
        "text": text,
        "parse_mode": "HTML",
        "reply_markup": {
            "inline_keyboard": [[
                {
                    "text": "📝 Ko'rish va Tasdiqlash",
                    "web_app": {"url": web_app_url}
                }
            ]]
        }
    }
    
    try:
        response = requests.post(f"{BASE_URL}/sendMessage", json=payload)
        # Log uchun natijani ko'rish
        if response.status_code != 200:
            print(f"Telegramga yuborishda xatolik: {response.text}")
    except Exception as e:
        print(f"Error sending msg: {e}")

def send_telegram_message(chat_id, text):
    """Oddiy xabar yuborish uchun (masalan 'Start' bosganda)"""
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML"
    }
    try:
        requests.post(f"{BASE_URL}/sendMessage", json=payload)
    except Exception as e:
        print(f"Error sending simple msg: {e}")