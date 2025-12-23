from django.db.models import Sum, Count, Q
from django.contrib.auth.decorators import user_passes_test
from django.shortcuts import render

from .models import Shop, Client, Debt


# Faqat Superuser kira oladi (Oddiy admin kira olmaydi)
@user_passes_test(lambda u: u.is_superuser)
def super_dashboard(request):
    # 1. DO'KONLAR STATISTIKASI
    shops = Shop.objects.annotate(
        client_count=Count('clients'),
        total_debt_uzs=Sum('clients__debt__amount_uzs',
                           filter=Q(clients__debt__transaction_type='debt', clients__debt__status='confirmed')),
        total_payment_uzs=Sum('clients__debt__amount_uzs',
                              filter=Q(clients__debt__transaction_type='payment', clients__debt__status='confirmed'))
    ).order_by('-created_at')

    # 2. GLOBAL STATISTIKA
    total_shops = shops.count()
    active_shops = shops.filter(is_active=True).count()

    # Platformadagi jami nasiya savdosi (Barcha do'konlar yig'indisi)
    global_turnover = Debt.objects.filter(transaction_type='debt', status='confirmed').aggregate(Sum('amount_uzs'))[
                          'amount_uzs__sum'] or 0

    context = {
        'shops': shops,
        'total_shops': total_shops,
        'active_shops': active_shops,
        'inactive_shops': total_shops - active_shops,
        'global_turnover': global_turnover,
    }

    return render(request, 'super_dashboard.html', context)