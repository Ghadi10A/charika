from django import template

register = template.Library()

@register.filter
def is_arabic(language_code):
    return language_code == 'ar'