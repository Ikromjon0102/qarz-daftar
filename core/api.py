# import time  # Vaqtni to'xtatib turish uchun
# from django.contrib import messages  # Ekranga chiroyli xabar chiqarish uchun
# from django.contrib.auth.decorators import login_required
# from django.shortcuts import redirect, render
#
# from core.models import Client
# from core.views import send_tg_msg
#
#
# @login_required(login_url='/login/')  # Faqat admin kira olsin
# def broadcast_view(request):
#     if request.method == 'POST':
#         text = request.POST.get('message')
#
#         if text:
#             # 1. Telegrami bor mijozlarni olamiz
#             # telegram_id__isnull=False -> Telegrami borlar
#             # exclude(telegram_id=0) -> ID si 0 bo'lmaganlar
#             clients = Client.objects.filter(telegram_id__isnull=False).exclude(telegram_id=0)
#
#             success_count = 0
#             fail_count = 0
#
#             for client in clients:
#                 try:
#                     # Xabarni yuboramiz
#                     send_tg_msg(client.telegram_id, text)
#                     success_count += 1
#
#                     # Telegram serverini "qiynamaslik" uchun 0.05 sekund kutamiz
#                     time.sleep(0.05)
#                 except Exception as e:
#                     fail_count += 1
#                     print(f"Xatolik ({client.full_name}): {e}")
#
#             # 2. Natijani chiqaramiz
#             messages.success(request, f"✅ Xabar yuborildi: {success_count} ta muvaffaqiyatli, {fail_count} ta xato.")
#             return redirect('main_menu')
#
#     return render(request, 'broadcast.html', {'back_url':'back_url'})


import threading  # <--- YANGI KUCH
import time
from django.contrib import messages
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required

from config import settings
from .models import Client
from .views import send_tg_msg


# send_tg_msg funksiyasini chaqirib olish kerak (agar pastda bo'lsa, tepaga olib chiqing yoki shu faylda ekanligiga ishonch hosil qiling)

# --- ORQA FONDA ISHLAYDIGAN FUNKSIYA ---
def send_broadcast_thread(text, admin_tg_id=None):
    """Bu funksiya foydalanuvchini kuttirmaydi, orqada ishlaydi"""
    clients = Client.objects.filter(telegram_id__isnull=False).exclude(telegram_id=0)

    success = 0
    fail = 0

    for client in clients:
        try:
            send_tg_msg(client.telegram_id, text)
            success += 1
            time.sleep(0.05)  # Spam bo'lmasligi uchun pauza
        except:
            fail += 1

    # Ish tugagach, ADMINGA hisobot yuboramiz (Telegramdan)
    if admin_tg_id:
        report = (
            f"✅ <b>Tarqatma tugadi!</b>\n\n"
            f"Jami urinish: {success + fail}\n"
            f"Yuborildi: {success}\n"
            f"O'xshamadi: {fail}"
        )
        send_tg_msg(admin_tg_id, report)
    print(f"Broadcast tugadi: {success} ok, {fail} error")


# --- ASOSIY VIEW ---
@login_required(login_url='/auth/telegram-login/')
def broadcast_view(request):
    if request.method == 'POST':
        text = request.POST.get('message')

        if text:
            # Hozirgi adminning telegram ID sini olamiz (Hisobot uchun)
            # Agar superuser bo'lsa va Client modeliga bog'lanmagan bo'lsa,
            # settings.ALLOWED_ADMIN_IDS dan olish mumkin.
            # Hozircha oddiyroq qilib settingsdan olamiz:
            admin_id = settings.ALLOWED_ADMIN_IDS[0]

            # THREAD (IP) ni ishga tushiramiz
            task = threading.Thread(
                target=send_broadcast_thread,
                args=(text, admin_id)
            )
            task.start()  # <-- KETDI! Saytni ushlab turmaydi

            # Ekranga darrov javob qaytaramiz
            messages.success(request, "🚀 Xabar yuborish fon rejimida boshlandi! Natijani Telegramda olasiz.")
            return redirect('dashboard')

    return render(request, 'broadcast.html', {'back_url': 'main_menu',})


# core/views.py

from .models import AllowedAdmin
from django.db.models import Q


# 2. ID QO'SHISH VA O'CHIRISH (Dashboard uchun)
@login_required(login_url='/auth/telegram-login/')
def manage_admins_view(request, action=None, admin_id=None):
    # ID Qo'shish
    if action == 'add' and request.method == 'POST':
        name = request.POST.get('name')
        tg_id = request.POST.get('telegram_id')
        try:
            AllowedAdmin.objects.create(name=name, telegram_id=tg_id)
            messages.success(request, f"✅ {name} adminlarga qo'shildi.")
        except:
            messages.error(request, "❌ Bu ID allaqachon mavjud!")

    # ID O'chirish
    elif action == 'delete' and admin_id:
        AllowedAdmin.objects.filter(id=admin_id).delete()
        messages.warning(request, "🗑 Admin o'chirildi.")

    # --- O'ZGARISH: Dashboardga emas, SETTINGS ga qaytaramiz ---
    return redirect('admin_control')


def admin_control(request):
    allowed_admins = AllowedAdmin.objects.all().order_by('-created_at')  # <--- QO'SHILDI
    return render(request, 'admin_control.html', {
        'back_url': 'main_menu',
        'allowed_admins': allowed_admins,
    })