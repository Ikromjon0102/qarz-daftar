from django.urls import path
from . import views, api

urlpatterns = [
    # 1. Sotuvchi oynasi
    path('login/', views.login_page_view, name='login_page'),
    path('auth/telegram-login/', views.telegram_auth_view, name='telegram_auth'),
    path('main/', views.main_menu_view, name='main_menu'),

    path('', views.login_page_view, name='landing_page'), # Glavniy sahifa
    path('signup/', api.signup_view, name='signup'),

    path('my-cabinet/', views.client_cabinet_view, name='client_cabinet'),
    path('client/<int:client_id>/', views.admin_client_detail_view, name='admin_client_detail'),
    path('create-payment/', views.create_payment_view, name='create_payment'),    
    path('dashboard/', views.dashboard_view, name='dashboard'),   
    path('manage-debt/<uuid:debt_uuid>/<str:action>/', views.manage_debt_view, name='manage_debt'),
    path('debt/<uuid:debt_uuid>/', views.debt_detail_view, name='debt_detail'),
    path('settings/', views.settings_view, name='settings'),

    path('create-debt/', views.create_debt_view, name='create_debt'),
    path('clients/', views.client_list_view, name='client_list'),
    path('clients/add/', views.client_form_view, name='client_add'),
    path('clients/<int:client_id>/edit/', views.client_form_view, name='client_edit'),
    path('clients/<int:client_id>/reset-tg/', views.client_reset_telegram_view, name='client_reset_tg'),

    path('webhook/', views.telegram_webhook, name='telegram_webhook'),

    path('broadcast/', api.broadcast_view, name='broadcast'),

    path('admins/<str:action>/', api.manage_admins_view, name='manage_admins'),
    path('admins/', api.admin_control, name='admin_control'),
    path('admins/<str:action>/<int:admin_id>/', api.manage_admins_view, name='manage_admins_id'),
]