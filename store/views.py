# store/views.py
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from .models import Product, Category
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from .models import Product
import json

@login_required(login_url='/auth/telegram-login/')
def shop_home(request):
    products = Product.objects.filter(is_active=True)
    categories = Category.objects.all()


    cart = request.session.get('cart', {})
    return render(request, 'store/product_list.html', {
        'products': products,
        'cart': cart,
        'categories': categories,
        'back_url': 'dashboard'  # Asosiy menyuga qaytish
    })


@require_POST
def decrease_cart(request, product_id):
    cart = request.session.get('cart', {})
    product_id = str(product_id)

    if product_id in cart:
        cart[product_id] -= 1
        # Agar 0 bo'lib qolsa, o'chirib tashlaymiz
        if cart[product_id] <= 0:
            del cart[product_id]

    request.session['cart'] = cart

    # Qaytaradigan ma'lumotimiz (yangi soni va umumiy savat soni)
    qty = cart.get(product_id, 0)
    total_items = sum(cart.values())

    return JsonResponse({'status': 'ok', 'qty': qty, 'total_items': total_items})


@require_POST
def add_to_cart(request, product_id):
    # Savatni sessiyadan olamiz (agar yo'q bo'lsa bo'sh lug'at {})
    cart = request.session.get('cart', {})

    # ID string bo'lishi kerak (sessiya JSON bo'lib saqlanadi)
    product_id = str(product_id)

    # Agar avval bor bo'lsa, sonini oshiramiz, yo'q bo'lsa 1 deymiz
    if product_id in cart:
        cart[product_id] += 1
    else:
        cart[product_id] = 1

    # Sessiyani yangilaymiz
    request.session['cart'] = cart

    # Jami nechta narsa borligini qaytaramiz (ikonka uchun)
    total_items = sum(cart.values())

    qty = cart[product_id]  # Yangi son
    return JsonResponse({'status': 'ok', 'total_items': total_items, 'qty': qty})


@login_required(login_url='/auth/telegram-login/')
def cart_detail(request):
    cart = request.session.get('cart', {})
    items = []
    total_price = 0

    # Savatdagi ID lar bo'yicha tovarlarni bazadan olamiz
    products = Product.objects.filter(id__in=cart.keys())

    for product in products:
        qty = cart[str(product.id)]
        total = product.price * qty
        total_price += total

        items.append({
            'product': product,
            'qty': qty,
            'total': total
        })

    return render(request, 'store/cart.html', {
        'items': items,
        'total_price': total_price,
        'back_url': 'shop_home'
    })


# Savatni tozalash (Buyurtma bergandan keyin yoki bekor qilganda)
def clear_cart(request):
    if 'cart' in request.session:
        del request.session['cart']
    return redirect('shop_home')