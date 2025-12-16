import requests
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from .models import Client, Debt
from django.utils import timezone
from datetime import timedelta
from .models import Settings
from django.contrib.auth import login
from django.contrib.auth.models import User
from django.views.decorators.csrf import csrf_exempt
from django.db.models import Sum, Q

def login_page_view(request):
    if request.user.is_authenticated:
        return redirect('main_menu')
    return render(request, 'login_loader.html')


@csrf_exempt
def telegram_auth_view(request):
    # --- 1. AGAR TUGMA BOSILIB KIRILSA (GET) ---
    # Bu qism `login_loader.html` ni ochib beradi
    if request.method == 'GET':
        return render(request, 'login_loader.html')

    # --- 2. AGAR LOADER JS ORQALI MA'LUMOT YUBORSA (POST) ---
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            telegram_id = int(data.get('telegram_id'))

            # A) ADMINMI?
            if telegram_id in settings.ALLOWED_ADMIN_IDS:
                user = User.objects.filter(is_superuser=True).first()
                if user:
                    login(request, user)
                    return JsonResponse({'status': 'ok', 'redirect_url': '/'})

            # B) MIJOZMI?
            client = Client.objects.filter(telegram_id=telegram_id).first()
            if client:
                request.session['client_id'] = client.id
                return JsonResponse({'status': 'ok', 'redirect_url': '/my-cabinet/'})

            # C) HECH KIM EMAS
            return JsonResponse({'status': 'error', 'msg': 'Siz ro\'yxatdan o\'tmagansiz'}, status=403)

        except Exception as e:
            print(f"Auth error: {e}")
            return JsonResponse({'status': 'error'}, status=400)

    return JsonResponse({'status': 'error'}, status=405)


@login_required(login_url='/login/')
def main_menu_view(request):
    return render(request, 'main_menu.html')

@login_required(login_url='/login/')
def create_debt_view(request):
    selected_client = None
    client_id_param = request.GET.get('client_id')
    if client_id_param:
        selected_client = Client.objects.filter(id=client_id_param).first()

    if request.method == 'POST':
        client_id = request.POST.get('client_id')
        
        # Ro'yxatlar
        names = request.POST.getlist('item_name[]')
        qtys = request.POST.getlist('item_qty[]')
        prices = request.POST.getlist('item_price[]')
        currencies = request.POST.getlist('item_currency[]')
        
        # Summalarni to'g'ri formatga o'tkazish
        try:
            total_uzs = float(request.POST.get('total_uzs', 0))
        except (ValueError, TypeError):
            total_uzs = 0
            
        try:
            total_usd = float(request.POST.get('total_usd', 0))
        except (ValueError, TypeError):
            total_usd = 0

        if client_id and names:
            client = get_object_or_404(Client, id=client_id)
            
            items_desc_list = []
            
            for name, qty, price, curr in zip(names, qtys, prices, currencies):
                if name:
                    q = float(qty)
                    p = float(price)
                    # Butun son bo'lsa .0 ni olib tashlaymiz
                    q = int(q) if q.is_integer() else q
                    p = int(p) if p.is_integer() else p

                    if curr == 'USD':
                        items_desc_list.append(f"🔹 {name}: {q}ta x ${p} = ${q*p}")
                    else:
                        items_desc_list.append(f"🔸 {name}: {q}ta x {p:,} = {q*p:,}")

            full_description = "\n".join(items_desc_list)

            # Bazaga yozish
            debt = Debt.objects.create(
                client=client,
                amount_uzs=total_uzs,
                amount_usd=total_usd,
                items=full_description,
                status='pending' # Bot orqali tasdiqlanishi kerak
            )
            
            # Signal orqali Telegramga xabar ketadi...
            messages.success(request, "Nasiya yuborildi!")
            
            # MUHIM: Ish bitgach, yana o'sha mijozning profiliga qaytamiz
            return redirect('admin_client_detail', client_id=client.id)

    clients = Client.objects.all().order_by('full_name')
    current_rate = Settings.get_solo().usd_rate
    return render(request, 'create_debt.html', {
        'clients': clients, 
        'back_url': 'main_menu',
        'selected_client': selected_client,
        'current_rate': current_rate # <--- Shablonga uzatamiz
    })

@login_required(login_url='/login/')
def create_payment_view(request):
    selected_client = None
    client_id_param = request.GET.get('client_id')
    if client_id_param:
        selected_client = Client.objects.filter(id=client_id_param).first()

    if request.method == 'POST':
        client_id = request.POST.get('client_id')
        
        # Bo'sh kelsa 0 deb olamiz
        try:
            amount_uzs = float(request.POST.get('amount_uzs') or 0)
        except ValueError: amount_uzs = 0
        
        try:
            amount_usd = float(request.POST.get('amount_usd') or 0)
        except ValueError: amount_usd = 0
        
        if client_id and (amount_uzs > 0 or amount_usd > 0):
            client = get_object_or_404(Client, id=client_id)
            
            # To'lovni MINUS bilan yozamiz
            Debt.objects.create(
                client=client,
                amount_uzs = -amount_uzs, 
                amount_usd = -amount_usd,
                items = "💵 To'lov qabul qilindi",
                status = 'confirmed', 
                transaction_type = 'payment'
            )
            
            messages.success(request, "To'lov qabul qilindi!")
            # Yana mijoz profiliga qaytamiz
            return redirect('admin_client_detail', client_id=client.id)

    clients = Client.objects.all().order_by('full_name')
    return render(request, 'create_payment.html', {
        'clients': clients,
        'back_url': 'main_menu',
        'selected_client': selected_client # Shablonga uzatamiz
    })

@login_required(login_url='/login/')
def manage_debt_view(request, debt_uuid, action):
    debt = get_object_or_404(Debt, uuid=debt_uuid)
    
    # 1. QAYTA YUBORISH (Agar xabar bormagan bo'lsa)
    if action == 'resend':
        if debt.status == 'pending':
            # Telegramga signal yuboramiz
            domain = request.get_host()
            # bot_utils dagi funksiyani chaqiramiz
            from .bot_utils import send_confirmation_request
            if debt.client.telegram_id:
                send_confirmation_request(debt.client.telegram_id, debt, domain)
                messages.success(request, "Tasdiqlash so'rovi qayta yuborildi!")
            else:
                messages.error(request, "Mijozning Telegrami ulanmagan!")
    
    # 2. MAJBURIY TASDIQLASH (Admin Override)
    elif action == 'force_confirm':
        debt.status = 'confirmed'
        debt.save()
        messages.success(request, "Qarz majburiy tasdiqlandi (Admin)!")

    # 3. O'CHIRIB TASHLASH (Bekor qilish)
    elif action == 'delete':
        debt.delete()
        messages.warning(request, "Qarz o'chirib tashlandi.")

    # Ish bitgach, yana mijoz profiliga qaytamiz
    return redirect('admin_client_detail', client_id=debt.client.id)

def debt_detail_view(request, debt_uuid):
    debt = get_object_or_404(Debt, uuid=debt_uuid)
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if debt.status != 'pending':
            # Agar allaqachon bosib bo'lgan bo'lsa
            return render(request, 'status_page.html', {
                'title': 'Eskirgan havola',
                'msg': f"Bu so'rov allaqachon {debt.get_status_display().lower()} bo'lgan.",
                'icon': 'fa-circle-info',
                'color': 'text-warning'
            })

        if action == 'confirm':
            debt.status = 'confirmed'
            debt.save()
            return render(request, 'status_page.html', {
                'title': 'Muvaffaqiyatli!',
                'msg': 'Siz nasiyani tasdiqladingiz. Rahmat!',
                'icon': 'fa-circle-check',
                'color': 'text-success'
            })
            
        elif action == 'reject':
            debt.status = 'rejected'
            debt.save()
            return render(request, 'status_page.html', {
                'title': 'Rad etildi',
                'msg': 'Siz nasiyani rad etdingiz.',
                'icon': 'fa-circle-xmark',
                'color': 'text-danger'
            })
            
    return render(request, 'debt_confirm.html', {'debt': debt})

@login_required(login_url='/login/')
def dashboard_view(request):
    now = timezone.now()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    
    # 1. CLIENTLAR RO'YXATI (BALANS) - Bu o'zgarishsiz qoladi
    # Bu yerda plyus va minus birga hisoblanaveradi, chunki bu QARZ QOLDIG'I
    clients = Client.objects.annotate(
        total_debt_uzs=Sum('debt__amount_uzs', filter=Q(debt__status='confirmed')),
        total_debt_usd=Sum('debt__amount_usd', filter=Q(debt__status='confirmed'))
    ).order_by('-total_debt_uzs')

    # 2. STATISTIKA (ALOHIDA-ALOHIDA)
    
    # A) BU OYLIK NASIYA SAVDO (Faqat 'debt' turi)
    # Bu do'kondan qancha tovar chiqib ketganini bildiradi
    monthly_sales_uzs = Debt.objects.filter(
        status='confirmed', 
        transaction_type='debt', 
        created_at__gte=month_start
    ).aggregate(Sum('amount_uzs'))['amount_uzs__sum'] or 0
    
    monthly_sales_usd = Debt.objects.filter(
        status='confirmed', 
        transaction_type='debt', 
        created_at__gte=month_start
    ).aggregate(Sum('amount_usd'))['amount_usd__sum'] or 0

    # B) BU OYLIK TUSHUM (Faqat 'payment' turi)
    # Bu cho'ntakka qancha pul kirganini bildiradi. 
    # Bazada minus turibdi, shuning uchun abs() qilib musbat qilamiz.
    monthly_income_uzs = Debt.objects.filter(
        status='confirmed', 
        transaction_type='payment', 
        created_at__gte=month_start
    ).aggregate(Sum('amount_uzs'))['amount_uzs__sum'] or 0
    
    monthly_income_usd = Debt.objects.filter(
        status='confirmed', 
        transaction_type='payment', 
        created_at__gte=month_start
    ).aggregate(Sum('amount_usd'))['amount_usd__sum'] or 0

    stats = {
        'sales_uzs': monthly_sales_uzs,
        'sales_usd': monthly_sales_usd,
        'income_uzs': abs(monthly_income_uzs), # Musbat qilamiz
        'income_usd': abs(monthly_income_usd), # Musbat qilamiz
    }

    return render(request, 'dashboard.html', {
        'clients': clients,
        'stats': stats,
        'back_url': 'main_menu'
    })

@login_required(login_url='/login/')
def admin_client_detail_view(request, client_id):
    client = get_object_or_404(Client, id=client_id)
    
    # Hamma operatsiyalar (Pendinglar ham ko'rinsin, admin bilsin)
    debts = Debt.objects.filter(client=client).order_by('-created_at')
    
    # Balansni hisoblaymiz (Faqat Confirmed)
    confirmed_debts = debts.filter(status='confirmed')
    stats = confirmed_debts.aggregate(
        sum_uzs=Sum('amount_uzs'),
        sum_usd=Sum('amount_usd')
    )
    
    total_uzs = stats['sum_uzs'] or 0
    total_usd = stats['sum_usd'] or 0

    return render(request, 'admin_client_detail.html', {
        'client': client,
        'debts': debts,
        'total_uzs': total_uzs,
        'total_usd': total_usd,
        'back_url': 'dashboard' # Orqaga qaytish Dashboardga
    })

def client_cabinet_view(request):
    client_id = request.session.get('client_id')
    if not client_id: return redirect('login_page')
    client = get_object_or_404(Client, id=client_id)
    
    # Sanalar
    now = timezone.now()
    month_start = now - timedelta(days=30)

    # Hamma qarzlari
    debts = Debt.objects.filter(client=client, status='confirmed').order_by('-created_at')
    
    # Jami qarz (Balans)
    totals = debts.aggregate(sum_uzs=Sum('amount_uzs'), sum_usd=Sum('amount_usd'))

    # YANGI: Shu oydagi xarajatlari
    month_totals = debts.filter(created_at__gte=month_start).aggregate(
        m_uzs=Sum('amount_uzs'), 
        m_usd=Sum('amount_usd')
    )

    context = {
        'client': client,
        'debts': debts[:20], 
        'total_uzs': totals['sum_uzs'] or 0,
        'total_usd': totals['sum_usd'] or 0,
        # Oylik statistika
        'month_uzs': month_totals['m_uzs'] or 0,
        'month_usd': month_totals['m_usd'] or 0,
    }
    return render(request, 'client_cabinet.html', context)


# core/views.py

import json
import requests
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from django.conf import settings
from django.utils import timezone

# Modellarni import qilamiz
from .models import Client, Debt
# Agar Order store app ichida bo'lsa:
from store.models import Order

@csrf_exempt
def telegram_webhook(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            
            # --------------------------------------------------
            # 1. AGAR ODDIY XABAR KELSA (MESSAGE)
            # --------------------------------------------------
            if 'message' in data:
                chat_id = data['message']['chat']['id']
                text = data['message'].get('text', '')

                # A) LOGIN (SSILKA)
                if text.startswith('/start '):
                    token = text.split(' ')[1]
                    try:
                        client = Client.objects.filter(invite_token=token).first()
                        if client:
                            client.telegram_id = chat_id
                            client.invite_token = None
                            client.save()
                            msg = f"🎉 <b>Tabriklaymiz, {client.full_name}!</b>\n\nSizning hisobingiz muvaffaqiyatli ulandi."
                        else:
                            msg = "❌ <b>Xatolik!</b>\nBu ssilka eskirgan yoki noto'g'ri."
                    except Exception as e:
                        msg = "❌ Tizim xatoligi."
                        print(f"Link error: {e}")
                    
                    send_tg_msg(chat_id, msg)
                    if client:
                        send_menu(chat_id, request.get_host())

                # B) START
                elif text == '/start':
                    send_menu(chat_id, request.get_host())

            # --------------------------------------------------
            # 2. AGAR KNOPKA BOSILSA (CALLBACK_QUERY)
            # --------------------------------------------------
            elif 'callback_query' in data:
                callback = data['callback_query']
                chat_id = callback['message']['chat']['id']
                message_id = callback['message']['message_id']
                data_text = callback['data'] # Masalan: "order_accept_5"
                callback_id = callback['id']

                print(f"🔘 Callback keldi: {data_text}") # DEBUG UCHUN

                # A) NASIYAGA YOZISH (TASDIQLASH)
                if data_text.startswith('order_accept_'):
                    order_id = data_text.split('_')[2]
                    handle_order_accept(chat_id, message_id, order_id)

                # B) BEKOR QILISH (OTMEN)
                elif data_text.startswith('order_reject_'):
                    order_id = data_text.split('_')[2]
                    handle_order_reject(chat_id, message_id, order_id)
                
                # Telegramga "Knopka bosildi" deb javob qaytaramiz (Loading to'xtaydi)
                answer_callback(callback_id)

            return JsonResponse({'status': 'ok'})

        except Exception as e:
            print(f"❌ Webhook Glavnaya Xatolik: {e}") # Xatoni terminalda ko'rish uchun
            return JsonResponse({'status': 'error'})
            
    return JsonResponse({'status': 'error'}, status=405)


# --- LOGIKA FUNKSIYALARI ---

def handle_order_accept(chat_id, message_id, order_id):
    print(f"✅ Order #{order_id} qabul qilinmoqda...")
    try:
        order = Order.objects.get(id=order_id)
        
        # Agar status 'new' bo'lmasa, demak allaqachon bosilgan
        if order.status != 'new':
            print("⚠️ Bu order allaqachon o'zgargan")
            answer_callback_text(chat_id, "Bu buyurtma allaqachon ishlov berilgan!")
            # Xabarni yangilab qo'yamiz baribir
            edit_tg_message(chat_id, message_id, f"⚠️ Bu buyurtma holati: {order.get_status_display()}")
            return

        # 1. Order statusini o'zgartiramiz
        order.status = 'accepted'
        order.save()
        
        # 2. QARZ (DEBT) YARATAMIZ 
        items_desc = f"🛒 Buyurtma #{order.id} (Online):\n"
        for item in order.orderitem_set.all():
            p_name = item.product.name if item.product else "Noma'lum"
            items_desc += f"- {p_name} ({item.qty}x)\n"
            
        Debt.objects.create(
            client=order.client,
            amount_uzs=order.total_price,
            amount_usd=0,
            items=items_desc,
            status='confirmed',
            transaction_type='debt'
        )
        print("✅ Debt yaratildi!")
        
        # 3. Xabarni yangilaymiz
        new_text = (
            f"✅ <b>QABUL QILINDI</b>\n"
            f"👤 {order.client.full_name}\n"
            f"💰 {order.total_price:,.0f} so'm nasiyaga yozildi."
        )
        edit_tg_message(chat_id, message_id, new_text)
        
        # 4. Mijozga xabar (Ixtiyoriy)
        if order.client.telegram_id:
             send_tg_msg(order.client.telegram_id, f"✅ Buyurtmangiz (#{order.id}) qabul qilindi.")

    except Order.DoesNotExist:
        print("❌ Order topilmadi bazadan")
        edit_tg_message(chat_id, message_id, "❌ Buyurtma topilmadi.")
    except Exception as e:
        print(f"❌ handle_order_accept ichida xato: {e}")


def handle_order_reject(chat_id, message_id, order_id):
    print(f"❌ Order #{order_id} bekor qilinmoqda...")
    try:
        order = Order.objects.get(id=order_id)
        
        if order.status != 'new':
            edit_tg_message(chat_id, message_id, f"⚠️ Bu buyurtma allaqachon {order.get_status_display()} bo'lgan!")
            return

        # 1. Statusni bekor qilish
        order.status = 'rejected'
        order.save()
        
        # 2. Xabarni yangilash
        new_text = (
            f"❌ <b>BEKOR QILINDI</b>\n"
            f"👤 {order.client.full_name}\n"
            f"Buyurtma rad etildi."
        )
        edit_tg_message(chat_id, message_id, new_text)

    except Order.DoesNotExist:
        edit_tg_message(chat_id, message_id, "❌ Buyurtma topilmadi.")
    except Exception as e:
        print(f"❌ handle_order_reject ichida xato: {e}")


# --- TELEGRAM API YORDAMCHILARI ---

def answer_callback(callback_id):
    """Loadingni to'xtatish"""
    try:
        url = f"https://api.telegram.org/bot{settings.BOT_TOKEN}/answerCallbackQuery"
        requests.post(url, json={"callback_query_id": callback_id})
    except Exception as e:
        print(f"answer_callback error: {e}")

def answer_callback_text(callback_id, text):
    """Ekranda kichik xabar ko'rsatish (Toast)"""
    try:
        url = f"https://api.telegram.org/bot{settings.BOT_TOKEN}/answerCallbackQuery"
        requests.post(url, json={"callback_query_id": callback_id, "text": text, "show_alert": True})
    except Exception as e:
        print(f"answer_callback_text error: {e}")

def edit_tg_message(chat_id, message_id, new_text):
    """Xabarni tahrirlash"""
    try:
        url = f"https://api.telegram.org/bot{settings.BOT_TOKEN}/editMessageText"
        payload = {
            "chat_id": chat_id,
            "message_id": message_id,
            "text": new_text,
            "parse_mode": "HTML"
        }
        res = requests.post(url, json=payload)
        if res.status_code != 200:
            print(f"Telegram Edit Error: {res.text}")
    except Exception as e:
        print(f"edit_tg_message error: {e}")

def send_tg_msg(chat_id, text):
    try:
        url = f"https://api.telegram.org/bot{settings.BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML"
        }
        requests.post(url, json=payload)
    except Exception as e:
        print(f"Telegram send error: {e}")

def send_menu(chat_id, domain):
    try:
        url = f"https://api.telegram.org/bot{settings.BOT_TOKEN}/sendMessage"
        welcome_text = (
            "👋 <b>Nasiya Nazorati Tizimi</b>\n\n"
            "Shaxsiy kabinetingizga kirish uchun pastdagi tugmani bosing 👇"
        )
        payload = {
            "chat_id": chat_id,
            "text": welcome_text,
            "parse_mode": "HTML",
            "reply_markup": {
                "inline_keyboard": [[
                    {
                        "text": "🏠 Kabinetga kirish",
                        "web_app": {"url": f"https://{domain}/auth/telegram-login/"}
                    }
                ]]
            }
        }
        requests.post(url, json=payload)
    except Exception as e:
        print(f"Telegram menu error: {e}")


@login_required(login_url='/login/')
def settings_view(request):
    settings_obj = Settings.get_solo()
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        # 1. KUSNI YANGILASH
        if action == 'update_rate':
            new_rate = request.POST.get('usd_rate')
            if new_rate:
                settings_obj.usd_rate = new_rate
                settings_obj.save()
                messages.success(request, f"Kurs yangilandi: 1$ = {new_rate} so'm")

        # 2. YANGI ADMIN QO'SHISH (ID orqali)
        elif action == 'add_admin':
            new_id = request.POST.get('admin_id')
            if new_id:
                try:
                    # settings.py dagi ro'yxatni o'zgartira olmaymiz (fayl), 
                    # lekin bazada Admin model qilib saqlasak bo'lardi.
                    # Hozircha soddalik uchun faqat Client sifatida qo'shamiz va 
                    # kelajakda "Admin" modelini joriy qilamiz.
                    
                    # MVP varianti: Shunchaki xabar chiqaramiz (Hozircha qo'lda qilasiz deb)
                    messages.info(request, "Admin qo'shish uchun IT mutaxassisga bog'laning (Xavfsizlik uchun).")
                except Exception:
                    pass

    return render(request, 'settings.html', {
        'settings': settings_obj,
        'back_url': 'main_menu'
    })


@login_required(login_url='/login/')
def client_list_view(request):
    # Qidiruv (Search)
    search_query = request.GET.get('q', '')
    if search_query:
        clients = Client.objects.filter(
            Q(full_name__icontains=search_query) |
            Q(phone__icontains=search_query)
        ).order_by('full_name')
    else:
        clients = Client.objects.all().order_by('full_name')

    return render(request, 'client_list.html', {
        'clients': clients,
        'search_query': search_query,
        'back_url': 'settings'  # Sozlamalardan kiriladi
    })


@login_required(login_url='/login/')
def client_form_view(request, client_id=None):
    client = None
    if client_id:
        client = get_object_or_404(Client, id=client_id)

    if request.method == 'POST':
        full_name = request.POST.get('full_name')
        # Raqamdagi ortiqcha bo'sh joylarni olib tashlaymiz
        phone = request.POST.get('phone', '').replace(' ', '')

        if full_name and phone:

            if not client and Client.objects.filter(phone=phone).exists():
                existing_client = Client.objects.get(phone=phone)
                messages.error(request,
                               f"Xatolik! Bu raqam ({phone}) allaqachon '{existing_client.full_name}' nomiga ochilgan.")
                return render(request, 'client_form.html', {
                    'client': {'full_name': full_name, 'phone': phone},  # Kiritganini qaytarib beramiz
                    'back_url': 'client_list'
                })

            if client and Client.objects.filter(phone=phone).exclude(id=client.id).exists():
                messages.error(request, f"Xatolik! Bu raqam boshqa mijozga tegishli.")
                return render(request, 'client_form.html', {
                    'client': client,
                    'back_url': 'client_list'
                })

            if client:
                client.full_name = full_name
                client.phone = phone
                client.save()
                messages.success(request, "Mijoz ma'lumotlari yangilandi!")
            else:
                Client.objects.create(full_name=full_name, phone=phone)
                messages.success(request, "Yangi mijoz qo'shildi!")

            return redirect('client_list')

    return render(request, 'client_form.html', {
        'client': client,
        'back_url': 'client_list'
    })

@login_required(login_url='/login/')
def client_reset_telegram_view(request, client_id):
    client = get_object_or_404(Client, id=client_id)

    # Telegram ID ni o'chiramiz va Yangi Token beramiz
    client.telegram_id = None
    import uuid
    client.invite_token = uuid.uuid4()  # Yangi ssilka bo'lishi uchun
    client.save()

    messages.warning(request, "Telegram bog'lanishi uzildi. Yangi ssilka yuboring!")
    return redirect('client_edit', client_id=client.id)