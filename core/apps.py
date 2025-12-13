# from django.apps import AppConfig


# class CoreConfig(AppConfig):
#     name = 'core'


# core/apps.py

from django.apps import AppConfig

class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'  # Appingiz nomi (agar boshqa bo'lsa o'zgartiring)

    def ready(self):
        import core.signals  # <--- MANA SHU QATOR SHART!