from django.db.models.signals import post_save
from django.dispatch import receiver
# from django.contrib.sites.models import Site # Yoki settingsdan oling
from .models import Debt
from .bot_utils import send_confirmation_request

@receiver(post_save, sender=Debt)
def notify_on_create(sender, instance, created, **kwargs):
    if created and instance.status == 'pending':
        if instance.client.telegram_id:
            # PythonAnywhere domenini shu yerdan berasiz
            domain = "telapp.tunl.uz"
            send_confirmation_request(instance.client.telegram_id, instance, domain)
