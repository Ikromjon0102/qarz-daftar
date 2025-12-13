import uuid
from django.db import models

class Client(models.Model):
    full_name = models.CharField(max_length=100, verbose_name="F.I.SH")
    phone = models.CharField(max_length=15, unique=True, verbose_name="Telefon")
    telegram_id = models.BigIntegerField(null=True, blank=True, unique=True)
    
    # Mijozni taklif qilish uchun unikal token
    invite_token = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, null=True, blank=True)

    def __str__(self):
        status = "✅ Bog'langan" if self.telegram_id else "⏳ Kutilmoqda"
        return f"{self.full_name} ({self.phone}) - {status}"


class Debt(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Kutilmoqda'),
        ('confirmed', 'Tasdiqlandi'),
        ('rejected', 'Rad etildi'),
    )

    TYPE_CHOICES = (
        ('debt', 'Nasiya (Qarz)'),
        ('payment', 'To\'lov (Qaytarish)'),
    )
    transaction_type = models.CharField(max_length=10, choices=TYPE_CHOICES, default='debt')
    client = models.ForeignKey(Client, on_delete=models.CASCADE)
    amount_uzs = models.DecimalField(max_digits=15, decimal_places=0, default=0, verbose_name="So'm qismi")
    amount_usd = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name="Dollar qismi")
    
    items = models.TextField(verbose_name="Tovarlar ro'yxati")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    
    # Mini App sahifasi uchun xavfsiz ID
    uuid = models.UUIDField(default=uuid.uuid4, editable=False)

    def __str__(self):
        return f"{self.amount_uzs} so'm - {self.client.full_name}"


class Settings(models.Model):
    usd_rate = models.DecimalField(max_digits=10, decimal_places=2, default=12800, verbose_name="Dollar kursi")
    
    def save(self, *args, **kwargs):
        # Bazada faqat bitta zapis bo'lishini ta'minlaymiz
        self.pk = 1
        super(Settings, self).save(*args, **kwargs)

    @classmethod
    def get_solo(cls):
        obj, created = cls.objects.get_or_create(pk=1)
        return obj

    def __str__(self):
        return f"Kurs: {self.usd_rate}"