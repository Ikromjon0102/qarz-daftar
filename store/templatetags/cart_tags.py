from django import template

register = template.Library()

@register.filter
def get_cart_qty(cart, product_id):
    """Savatdan mahsulot sonini olib beradi"""
    # Sessiyada IDlar string bo'lib saqlanadi, shuning uchun str() qilamiz
    return cart.get(str(product_id), 0)