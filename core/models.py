# core/models.py
import uuid
from django.db import models
from django.contrib.auth.models import User


# --- 1. DO'KON MODELI ---
class Shop(models.Model):
    name = models.CharField(max_length=100, verbose_name="Do'kon nomi")
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='shops', verbose_name="Egasining logini")
    created_at = models.DateTimeField(auto_now_add=True)

    # Sozlamalar
    telegram_bot_token = models.CharField(max_length=100, blank=True, null=True, verbose_name="Bot Token")
    is_active = models.BooleanField(default=True, verbose_name="To'lov qilinganmi?")  # Obuna uchun

    def __str__(self):
        return self.name


# --- 2. ADMIN/XODIM PROFILI (YANGI) ---
class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    shop = models.ForeignKey(Shop, on_delete=models.CASCADE, verbose_name="Do'kon")
    role = models.CharField(max_length=20, choices=(('admin', 'Admin'), ('worker', 'Xodim')), default='admin')

    def __str__(self):
        return f"{self.user.username} - {self.shop.name}"


# --- 3. MIJOZ ---
class Client(models.Model):
    # Har bir mijoz qaysidir do'konga tegishli bo'lishi shart
    shop = models.ForeignKey(Shop, on_delete=models.CASCADE, related_name='clients', null=True, blank=True)

    full_name = models.CharField(max_length=100, verbose_name="F.I.SH")

    # DIQQAT: unique=True ni olib tashladik. Chunki A do'konda bor mijoz, B do'konda ham bo'lishi mumkin.
    phone = models.CharField(max_length=15, verbose_name="Telefon")
    telegram_id = models.BigIntegerField(null=True, blank=True)

    invite_token = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, null=True, blank=True)

    class Meta:
        # Bitta do'kon ichida telefon raqam takrorlanmasin
        unique_together = ('shop', 'phone')

    def __str__(self):
        status = "✅" if self.telegram_id else "⏳"
        return f"{self.full_name} ({self.phone}) {status}"


# --- 4. RUXSAT ETILGAN ADMINLAR (WHITELIST) ---
class AllowedAdmin(models.Model):
    shop = models.ForeignKey(Shop, on_delete=models.CASCADE, null=True, blank=True)  # <-- Qaysi do'konniki?
    name = models.CharField(max_length=100, verbose_name="Xodim Ismi")
    telegram_id = models.BigIntegerField(unique=True, verbose_name="Telegram ID")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.telegram_id})"


# --- 5. QARZ VA TO'LOVLAR ---
class Debt(models.Model):
    shop = models.ForeignKey(Shop, on_delete=models.CASCADE, related_name='debts', null=True, blank=True)  # <-- Do'kon

    STATUS_CHOICES = (
        ('pending', 'Kutilmoqda'),
        ('confirmed', 'Tasdiqlandi'),
        ('rejected', 'Rad etildi'),
    )
    TYPE_CHOICES = (
        ('debt', 'Nasiya (Qarz)'),
        ('payment', 'To\'lov (Qaytarish)'),
    )
    PAYMENT_METHOD_CHOICES = (
        ('cash', 'Naqd'),
        ('card', 'Plastik (Humo/Uzcard)'),
        ('click', 'Click / Payme'),
        ('transfer', 'Perechislenie'),
    )
    payment_method = models.CharField(
        max_length=20,
        choices=PAYMENT_METHOD_CHOICES,
        null=True,
        blank=True,
        verbose_name="To'lov turi"
    )
    transaction_type = models.CharField(max_length=10, choices=TYPE_CHOICES, default='debt')
    client = models.ForeignKey(Client, on_delete=models.CASCADE)
    amount_uzs = models.DecimalField(max_digits=15, decimal_places=0, default=0, verbose_name="So'm qismi")
    amount_usd = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name="Dollar qismi")

    items = models.TextField(verbose_name="Tovarlar ro'yxati")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)

    uuid = models.UUIDField(default=uuid.uuid4, editable=False)

    def __str__(self):
        return f"{self.amount_uzs} so'm - {self.client.full_name}"


# --- 6. SOZLAMALAR ---
class Settings(models.Model):
    # Har bir do'konning o'z sozlamasi bo'ladi
    shop = models.OneToOneField(Shop, on_delete=models.CASCADE, related_name='settings', null=True, blank=True)
    usd_rate = models.DecimalField(max_digits=10, decimal_places=2, default=12800, verbose_name="Dollar kursi")

    # get_solo va save metodlarini o'chiramiz, chunki endi bu Singleton emas.
    def __str__(self):
        return f"{self.shop.name} Sozlamalari"