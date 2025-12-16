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


class Order(models.Model):
    STATUS_CHOICES = (
        ('new', 'Yangi'),
        ('accepted', 'Qabul qilindi'),
        ('rejected', 'Bekor qilindi'),
    )
    client = models.ForeignKey(Client, on_delete=models.CASCADE, verbose_name="Mijoz")
    total_price = models.DecimalField(max_digits=12, decimal_places=0, default=0, verbose_name="Jami summa")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='new', verbose_name="Holat")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self): return f"Buyurtma #{self.id} - {self.client}"


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE)
    product = models.ForeignKey('Product', on_delete=models.SET_NULL, null=True)
    qty = models.IntegerField(default=1)
    price = models.DecimalField(max_digits=10, decimal_places=0) # O'sha vaqtdagi narx
    
    @property
    def total(self):
        return self.qty * self.price