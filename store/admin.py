# store/admin.py
from django.contrib import admin
from .models import Category, Product

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ['name', 'price', 'category', 'is_active']
    list_filter = ['category', 'is_active']
    search_fields = ['name']

admin.site.register(Category)