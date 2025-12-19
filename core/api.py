import threading  # <--- YANGI KUCH
import time
from django.contrib import messages
from django.contrib.auth.models import User
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from .models import Client, UserProfile, Shop, Settings
from .views import send_tg_msg, get_current_shop
from django.db import transaction


@login_required(login_url='/auth/telegram-login/')
def broadcast_view(request):
    shop = get_current_shop(request)
    if request.method == 'POST':
        text = request.POST.get('message')
        if text:
            # Faqat shu do'kon mijozlariga
            clients = Client.objects.filter(shop=shop, telegram_id__isnull=False).exclude(telegram_id=0)

            def send_thread(txt, cl_list):
                for c in cl_list:
                    try:
                        send_tg_msg(c.telegram_id, txt)
                        time.sleep(0.05)
                    except:
                        pass

            threading.Thread(target=send_thread, args=(text, clients)).start()
            messages.success(request, "Xabar yuborish boshlandi!")
            return redirect('dashboard')

    # return render(request, 'broadcast.html')

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
    shop = get_current_shop(request)
    allowed_admins = AllowedAdmin.objects.filter(shop=shop).order_by('-created_at')
    return render(request, 'admin_control.html', {
        'back_url': 'main_menu',
        'allowed_admins': allowed_admins,
    })


def signup_view(request):
    if request.method == 'POST':
        shop_name = request.POST.get('shop_name')
        admin_name = request.POST.get('admin_name')
        telegram_id = request.POST.get('telegram_id')

        # Validatsiya
        if User.objects.filter(username=telegram_id).exists():
            messages.error(request, "Bu Telegram ID bilan allaqachon do'kon ochilgan!")
            return redirect('landing_page')

        try:
            with transaction.atomic():  # Agar bittasi o'xshamasa, hammasini bekor qiladi
                # 1. User yaratamiz
                user = User.objects.create_user(username=telegram_id, password='1')  # Parol shartli

                # 2. Do'kon yaratamiz
                shop = Shop.objects.create(name=shop_name, owner=user)

                # 3. Profil va Adminlik
                UserProfile.objects.create(user=user, shop=shop, role='admin')
                AllowedAdmin.objects.create(shop=shop, name=admin_name, telegram_id=telegram_id)

                # 4. Sozlamalar
                Settings.objects.create(shop=shop, usd_rate=12800)

            # Muvaffaqiyatli!
            return render(request, 'signup_success.html', {
                'shop_name': shop_name,
                'bot_username': 'SizningBotingizUsername'  # Bot username shu yerga yoziladi
            })

        except Exception as e:
            messages.error(request, f"Xatolik yuz berdi: {e}")
            return redirect('landing_page')

    return redirect('landing_page')