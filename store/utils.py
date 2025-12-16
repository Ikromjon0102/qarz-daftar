# store/utils.py
import requests
from django.conf import settings

def send_order_to_admin(order, items):
    """
    Yangi buyurtma haqida Adminga xabar yuborish
    """
    token = settings.BOT_TOKEN
    # Adminlar ro'yxatidagi birinchi odamga (yoki guruhga) yuboramiz
    # Hozircha settings.ALLOWED_ADMIN_IDS dagi birinchi ID ga yuboramiz
    admin_id = settings.ALLOWED_ADMIN_IDS[0] 
    
    # 1. Xabar matnini yasaymiz
    text = f"📦 <b>Yangi Buyurtma! #{order.id}</b>\n"
    text += f"👤 Mijoz: <b>{order.client.full_name}</b>\n"
    text += f"📞 Tel: {order.client.phone}\n"
    text += "➖➖➖➖➖➖➖➖\n"
    
    for item in items:
        product_name = item.product.name if item.product else "O'chirilgan tovar"
        text += f"🔸 {product_name}\n"
        text += f"   {item.qty} x {item.price:,.0f} = <b>{item.total:,.0f} so'm</b>\n"
    
    text += "➖➖➖➖➖➖➖➖\n"
    text += f"💰 <b>JAMI: {order.total_price:,.0f} so'm</b>"

    # 2. Tugmalar (Tasdiqlash yoki Bekor qilish)
    # Callback data orqali keyinroq ushlaymiz: order_accept_ID yoki order_reject_ID
    reply_markup = {
        "inline_keyboard": [
            [
                {"text": "✅ Nasiyaga yozish", "callback_data": f"order_accept_{order.id}"}
            ],
            [
                {"text": "❌ Bekor qilish", "callback_data": f"order_reject_{order.id}"}
            ]
        ]
    }

    # 3. Yuborish
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": admin_id,
        "text": text,
        "parse_mode": "HTML",
        "reply_markup": reply_markup
    }
    
    try:
        requests.post(url, json=payload)
    except Exception as e:
        print(f"Telegram error: {e}")