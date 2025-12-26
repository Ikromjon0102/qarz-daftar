import json
import requests
import threading
import time
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from datetime import timedelta
from django.contrib.auth import login
from django.contrib.auth.models import User
from django.views.decorators.csrf import csrf_exempt
from django.db.models import Sum, Q
from django.conf import settings
from django.http import JsonResponse, HttpResponse


# Modellar
from .models import Client, Debt, Settings, AllowedAdmin, Shop, UserProfile
from store.models import Order, Product  # Agar kerak bo'lsa


def get_current_shop(request):
    """
    Tizimga kirgan adminning do'konini qaytaradi.
    """
    if not request.user.is_authenticated:
        return None
    try:
        # UserProfile orqali bog'langan do'konni olamiz
        return request.user.profile.shop
    except Exception:
        # Agar superuser bo'lsa va profili bo'lmasa (Admin panel uchun)
        if request.user.is_superuser:
            # Vaqtincha birinchi do'konni qaytarib turamiz yoki None
            return Shop.objects.first()
        return None


from django.shortcuts import render, redirect
from .models import Shop, UserProfile

def login_page_view(request):
    # 1. Eng avval: Foydalanuvchi tizimga kirganmi?
    if request.user.is_authenticated:
        
        # 2. U do'kon egasimi? (Shop jadvalidan qidiramiz)
        is_owner = Shop.objects.filter(owner=request.user).exists()
        
        # 3. Yoki u xodimmi? (UserProfile jadvalidan qidiramiz)
        is_worker = UserProfile.objects.filter(user=request.user).exists()

        # 4. Agar u Ega yoki Xodim bo'lsa -> Main Menuga o'tsin
        if is_owner or is_worker:
            return redirect('main_menu')
    
    # 5. Agar login qilmagan bo'lsa yoki do'koni yo'q bo'lsa -> Landing page
    return render(request, 'landing.html')


# 1. LOGIN LOGIKASINI SODDALASHTIRAMIZ
@csrf_exempt
def telegram_auth_view(request):
    """
    Telegram orqali kirishni tekshirish (SaaS versiya)
    """
    if request.method == 'GET':
        return render(request, 'login_loader.html')

    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            telegram_id = int(data.get('telegram_id'))

            # 1. XODIM / ADMIN SIFATIDA KIRISH
            # Biz "Admin qo'shish"da User username=telegram_id qilib ochganmiz
            user = User.objects.filter(username=str(telegram_id)).first()
            if user:
                login(request, user)
                return JsonResponse({'status': 'ok', 'redirect_url': '/'})

            # 2. PLATFORMA EGASI (Superuser)
            admins = AllowedAdmin.objects.filter(telegram_id=telegram_id)
            if telegram_id in admins:
                superuser = User.objects.filter(is_superuser=True).first()
                if superuser:
                    login(request, superuser)
                    return JsonResponse({'status': 'ok', 'redirect_url': '/'})

            # 3. MIJOZ SIFATIDA KIRISH
            # Mijoz qaysi do'konniki bo'lsa ham kiraveradi,
            # lekin client_cabinet faqat o'ziga tegishli narsani ko'rsatadi.
            client = Client.objects.filter(telegram_id=telegram_id).first()
            if client:
                request.session['client_id'] = client.id
                return JsonResponse({'status': 'ok', 'redirect_url': '/my-cabinet/'})

            return JsonResponse({'status': 'ok', 'redirect_url': '/login/'}, status=200)

        except Exception as e:
            print(f"Auth error: {e}")
            return JsonResponse({'status': 'error'}, status=400)
    return JsonResponse({'status': 'error'}, status=405)


@login_required(login_url='/login/')
def main_menu_view(request):
    # Faqat o'z do'koniga tegishli narsalar
    shop = get_current_shop(request)
    if not shop:
        return HttpResponse("Sizga do'kon biriktirilmagan!")

    return render(request, 'main_menu.html', {
        'shop': shop
    })



@login_required(login_url='/login/')
def create_debt_view(request):
    shop = get_current_shop(request)
    selected_client = None

    client_id_param = request.GET.get('client_id')
    if client_id_param:
        # Xavfsizlik: Faqat o'z do'koni mijozini tanlay olsin
        selected_client = Client.objects.filter(id=client_id_param, shop=shop).first()

    if request.method == 'POST':
        client_id = request.POST.get('client_id')

        # Ro'yxatlar
        names = request.POST.getlist('item_name[]')
        qtys = request.POST.getlist('item_qty[]')
        prices = request.POST.getlist('item_price[]')
        currencies = request.POST.getlist('item_currency[]')

        try:
            total_uzs = float(request.POST.get('total_uzs', 0))
        except:
            total_uzs = 0
        try:
            total_usd = float(request.POST.get('total_usd', 0))
        except:
            total_usd = 0

        if client_id and names:
            client = get_object_or_404(Client, id=client_id, shop=shop)

            items_desc_list = []
            for name, qty, price, curr in zip(names, qtys, prices, currencies):
                if name:
                    q = float(qty)
                    p = float(price)
                    q = int(q) if q.is_integer() else q
                    p = int(p) if p.is_integer() else p
                    if curr == 'USD':
                        items_desc_list.append(f"🔹 {name}: {q}ta x ${p} = ${q * p}")
                    else:
                        items_desc_list.append(f"🔸 {name}: {q}ta x {p:,} = {q * p:,}")

            full_description = "\n".join(items_desc_list)

            # BAZAGA YOZISH (shop=shop)
            debt = Debt.objects.create(
                shop=shop,  # <--- MUHIM
                client=client,
                amount_uzs=total_uzs,
                amount_usd=total_usd,
                items=full_description,
                status='pending'
            )

            messages.success(request, "Nasiya yuborildi!")
            return redirect('admin_client_detail', client_id=client.id)

    # Faqat shu do'kon mijozlari
    clients = Client.objects.filter(shop=shop).order_by('full_name')

    # Do'kon sozlamalaridan kursni olamiz
    settings_obj, _ = Settings.objects.get_or_create(shop=shop)
    current_rate = settings_obj.usd_rate

    return render(request, 'create_debt.html', {
        'clients': clients,
        'back_url': 'main_menu',
        'selected_client': selected_client,
        'current_rate': current_rate
    })

@login_required(login_url='/login/')
def create_payment_view(request):
    shop = get_current_shop(request)
    selected_client = None

    client_id_param = request.GET.get('client_id')
    if client_id_param:
        selected_client = Client.objects.filter(id=client_id_param, shop=shop).first()

    if request.method == 'POST':
        client_id = request.POST.get('client_id')
        payment_method = request.POST.get('payment_method')
        note = request.POST.get('note')

        try:
            amount_uzs = float(request.POST.get('amount_uzs') or 0)
        except:
            amount_uzs = 0
        try:
            amount_usd = float(request.POST.get('amount_usd') or 0)
        except:
            amount_usd = 0

        if client_id and (amount_uzs > 0 or amount_usd > 0):
            client = get_object_or_404(Client, id=client_id, shop=shop)

            method_names = {'cash': 'Naqd', 'card': 'Karta', 'click': 'Click', 'transfer': 'Perechislenie'}
            method_display = method_names.get(payment_method, '')
            description = f"💵 To'lov ({method_display})" if method_display else "💵 To'lov"
            if note: description += f" | {note}"

            Debt.objects.create(
                shop=shop,  # <--- MUHIM
                client=client,
                amount_uzs=-amount_uzs,
                amount_usd=-amount_usd,
                items=description,
                status='confirmed',
                transaction_type='payment',
                payment_method=payment_method
            )

            # Telegram xabar va boshqalar...
            current_balance = \
            Debt.objects.filter(shop=shop, client=client, status='confirmed').aggregate(Sum('amount_uzs'))[
                'amount_uzs__sum'] or 0
            if client.telegram_id:
                try:
                    msg = f"💸 <b>To'lov qabul qilindi!</b>\n\n👤 Mijoz: {client.full_name}\n💰 To'landi: <b>{amount_uzs:,.0f} so'm</b> ({method_display})\n"
                    if note: msg += f"📝 Izoh: {note}\n"
                    msg += "➖➖➖➖➖➖➖➖\n"
                    msg += f"📉 Qolgan qarz: <b>{current_balance:,.0f} so'm</b>"
                    send_tg_msg(client.telegram_id, msg)
                except Exception as e:
                    print(e)

            messages.success(request, f"✅ {client.full_name} dan to'lov qabul qilindi!")
            return redirect('admin_client_detail', client_id=client.id)

    clients = Client.objects.filter(shop=shop).order_by('full_name')

    return render(request, 'create_payment.html', {
        'clients': clients,
        'back_url': 'main_menu',
        'selected_client': selected_client
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
    shop = get_current_shop(request)
    if not shop: return redirect('login_page')

    now = timezone.now()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    # 1. DO'KON ADMINLARI
    allowed_admins = AllowedAdmin.objects.filter(shop=shop).order_by('-created_at')

    # 2. CLIENTLAR VA BALANS (Faqat shu do'kon uchun)
    clients = Client.objects.filter(shop=shop).annotate(
        total_debt_uzs=Sum('debt__amount_uzs', filter=Q(debt__status='confirmed')),
        total_debt_usd=Sum('debt__amount_usd', filter=Q(debt__status='confirmed'))
    ).order_by('-total_debt_uzs')

    # 3. STATISTIKA
    # A) Savdo (Nasiya)
    monthly_sales_uzs = Debt.objects.filter(
        shop=shop,
        status='confirmed',
        transaction_type='debt',
        created_at__gte=month_start
    ).aggregate(Sum('amount_uzs'))['amount_uzs__sum'] or 0

    monthly_sales_usd = Debt.objects.filter(
        shop=shop,
        status='confirmed',
        transaction_type='debt',
        created_at__gte=month_start
    ).aggregate(Sum('amount_usd'))['amount_usd__sum'] or 0

    # B) Tushum (To'lov)
    monthly_income_uzs = Debt.objects.filter(
        shop=shop,
        status='confirmed',
        transaction_type='payment',
        created_at__gte=month_start
    ).aggregate(Sum('amount_uzs'))['amount_uzs__sum'] or 0

    monthly_income_usd = Debt.objects.filter(
        shop=shop,
        status='confirmed',
        transaction_type='payment',
        created_at__gte=month_start
    ).aggregate(Sum('amount_usd'))['amount_usd__sum'] or 0

    stats = {
        'sales_uzs': monthly_sales_uzs,
        'sales_usd': monthly_sales_usd,
        'income_uzs': abs(monthly_income_uzs),
        'income_usd': abs(monthly_income_usd),
    }

    return render(request, 'dashboard.html', {
        'clients': clients,
        'stats': stats,
        'back_url': 'main_menu',
        'allowed_admins': allowed_admins,
        'shop': shop
    })


@login_required(login_url='/login/')
def admin_client_detail_view(request, client_id):
    shop = get_current_shop(request)
    # Faqat o'z mijozini ko'ra olsin
    client = get_object_or_404(Client, id=client_id, shop=shop)

    debts = Debt.objects.filter(client=client).order_by('-created_at')

    confirmed_debts = debts.filter(status='confirmed')
    stats = confirmed_debts.aggregate(sum_uzs=Sum('amount_uzs'), sum_usd=Sum('amount_usd'))

    return render(request, 'admin_client_detail.html', {
        'client': client,
        'debts': debts,
        'total_uzs': stats['sum_uzs'] or 0,
        'total_usd': stats['sum_usd'] or 0,
        'back_url': 'dashboard'
    })


def client_cabinet_view(request):
    client_id = request.session.get('client_id')
    if not client_id: return redirect('login_page')  # Login page nomini tekshiring (telegram_auth bo'lishi mumkin)

    client = get_object_or_404(Client, id=client_id)

    # Sanalar
    now = timezone.now()
    month_start = now - timedelta(days=30)

    # Hamma qarzlari (Bu yerda 'debts' deb nomlangan o'zgaruvchi aslida butun tarix)
    all_history = Debt.objects.filter(client=client, status='confirmed').order_by('-created_at')

    # Jami qarz (Balans)
    totals = all_history.aggregate(sum_uzs=Sum('amount_uzs'), sum_usd=Sum('amount_usd'))

    # YANGI: Shu oydagi xarajatlari
    month_totals = all_history.filter(created_at__gte=month_start).aggregate(
        m_uzs=Sum('amount_uzs'),
        m_usd=Sum('amount_usd')
    )

    search_query = request.GET.get('q', '')

    if search_query:
        all_history = all_history.filter(items__icontains=search_query)

    context = {
        'client': client,

        # --- O'ZGARISH SHU YERDA ---
        # HTML fayl 'history' ni kutmoqda, 'debts' ni emas.
        'history': all_history[:50],  # 20 ta kamlik qilishi mumkin, 50 qildim
        # ---------------------------

        'total_uzs': totals['sum_uzs'] or 0,
        'total_usd': totals['sum_usd'] or 0,
        'month_uzs': month_totals['m_uzs'] or 0,
        'month_usd': month_totals['m_usd'] or 0,
        'search_query': search_query,
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

            if 'message' in data:
                chat_id = data['message']['chat']['id']
                text = data['message'].get('text', '')

                if text.startswith('/start '):
                    token = text.split(' ')[1]
                    # Token orqali mijozni topamiz (u qaysi do'konda bo'lsa ham)
                    client = Client.objects.filter(invite_token=token).first()
                    if client:
                        client.telegram_id = chat_id
                        client.invite_token = None
                        client.save()
                        send_tg_msg(chat_id, f"🎉 {client.shop.name}: Xush kelibsiz, {client.full_name}!")
                        send_menu(chat_id, request.get_host())
                    else:
                        send_tg_msg(chat_id, "❌ Xato ssilka")
                elif text == '/start':
                    send_menu(chat_id, request.get_host())
                elif text in ['/id', '/myid']:
                    send_tg_msg(chat_id, f"🆔: {chat_id}")

            elif 'callback_query' in data:
                callback = data['callback_query']
                data_text = callback['data']
                chat_id = callback['message']['chat']['id']
                message_id = callback['message']['message_id']

                if data_text.startswith('order_accept_'):
                    order_id = data_text.split('_')[2]
                    handle_order_accept(chat_id, message_id, order_id)
                elif data_text.startswith('order_reject_'):
                    order_id = data_text.split('_')[2]
                    handle_order_reject(chat_id, message_id, order_id)

                answer_callback(callback['id'])

            return JsonResponse({'status': 'ok'})
        except Exception as e:
            print(e)
            return JsonResponse({'status': 'error'})
    return JsonResponse({'status': 'error'}, status=405)
# --- LOGIKA FUNKSIYALARI ---

def handle_order_accept(chat_id, message_id, order_id):
    try:
        order = Order.objects.get(id=order_id)
        if order.status != 'new':
            return

        order.status = 'accepted'
        order.save()

        items_desc = f"🛒 Buyurtma #{order.id}:\n"
        for item in order.orderitem_set.all():
            p_name = item.product.name if item.product else "Noma'lum"
            items_desc += f"- {p_name} ({item.qty}x)\n"

        # DEBT YARATISH (shop ni qo'shamiz)
        Debt.objects.create(
            shop=order.shop,  # <--- MUHIM
            client=order.client,
            amount_uzs=order.total_price,
            items=items_desc,
            status='confirmed',
            transaction_type='debt'
        )

        edit_tg_message(chat_id, message_id, f"✅ Qabul qilindi\n👤 {order.client.full_name}")
        if order.client.telegram_id:
            send_tg_msg(order.client.telegram_id, f"✅ Buyurtmangiz (#{order.id}) qabul qilindi.")

    except Order.DoesNotExist:
        pass
    except Exception as e:
        print(e)


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
    shop = get_current_shop(request)
    # Do'kon uchun alohida settings olamiz
    settings_obj, created = Settings.objects.get_or_create(shop=shop)

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'update_rate':
            new_rate = request.POST.get('usd_rate')
            if new_rate:
                settings_obj.usd_rate = new_rate
                settings_obj.save()
                messages.success(request, f"Kurs yangilandi: {new_rate}")

        elif action == 'add_admin':
            # YANGI ADMIN (XODIM) QO'SHISH
            name = request.POST.get('name')
            tg_id = request.POST.get('telegram_id')
            if name and tg_id:
                # 1. User yaratamiz (Login uchun)
                if not User.objects.filter(username=str(tg_id)).exists():
                    user = User.objects.create_user(username=str(tg_id), password='worker_password')
                    # 2. Uni shu do'konga bog'laymiz
                    UserProfile.objects.create(user=user, shop=shop, role='worker')
                    # 3. Ro'yxatga (Whitelist) qo'shamiz
                    AllowedAdmin.objects.create(shop=shop, name=name, telegram_id=tg_id)
                    messages.success(request, f"Xodim {name} qo'shildi!")
                else:
                    messages.error(request, "Bu Telegram ID band!")

    # Shu do'kon adminlari
    allowed_admins = AllowedAdmin.objects.filter(shop=shop)

    return render(request, 'settings.html', {
        'settings': settings_obj,
        'allowed_admins': allowed_admins,
        'back_url': 'main_menu',
    })



@login_required(login_url='/login/')
def client_list_view(request):
    shop = get_current_shop(request)
    search_query = request.GET.get('q', '')

    clients = Client.objects.filter(shop=shop)  # <--- Faqat o'z mijozlari

    if search_query:
        clients = clients.filter(
            Q(full_name__icontains=search_query) |
            Q(phone__icontains=search_query)
        ).order_by('full_name')
    else:
        clients = clients.order_by('full_name')

    return render(request, 'client_list.html', {
        'clients': clients,
        'search_query': search_query,
        'back_url': 'settings'
    })

@login_required(login_url='/login/')
def client_form_view(request, client_id=None):
    shop = get_current_shop(request)
    client = None
    if client_id:
        client = get_object_or_404(Client, id=client_id, shop=shop)

    if request.method == 'POST':
        full_name = request.POST.get('full_name')
        phone = request.POST.get('phone', '').replace(' ', '')

        if full_name and phone:
            # Unikallikni faqat SHU DO'KON ichida tekshiramiz
            if not client and Client.objects.filter(shop=shop, phone=phone).exists():
                messages.error(request, f"Xatolik! Bu raqam do'koningizda mavjud.")
                return render(request, 'client_form.html',
                              {'client': {'full_name': full_name, 'phone': phone}, 'back_url': 'client_list'})

            if client:
                client.full_name = full_name
                client.phone = phone
                client.save()
                messages.success(request, "Mijoz yangilandi!")
            else:
                Client.objects.create(shop=shop, full_name=full_name, phone=phone)
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

