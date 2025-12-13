# store/models.py
from django.db import models
from core.models import Client  # Mijoz kerak bo'ladi


class Category(models.Model):
    name = models.CharField(max_length=100, verbose_name="Kategoriya")

    def __str__(self): return self.name

    class Meta: verbose_name_plural = "Kategoriyalar"


class Product(models.Model):
    category = models.ForeignKey(Category, on_delete=models.CASCADE, null=True, verbose_name="Kategoriya")
    name = models.CharField(max_length=200, verbose_name="Nomi")
    description = models.TextField(blank=True, verbose_name="Tarif")
    price = models.DecimalField(max_digits=10, decimal_places=0, verbose_name="Narxi")
    image = models.ImageField(upload_to='products/', null=True, blank=True, verbose_name="Rasm")
    is_active = models.BooleanField(default=True, verbose_name="Sotuvda bormi?")

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self): return self.name

    class Meta: verbose_name = "Mahsulot"; verbose_name_plural = "Mahsulotlar"

# Buyurtma (Order) modellarini sal keyinroq qo'shsak ham bo'ladi, 
# avval mahsulotlarni chiqarib olaylik.