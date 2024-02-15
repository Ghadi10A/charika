from django import template

register = template.Library()

@register.filter
def has_reacted(post, user):
    return product.stars_feedback.filter(author=user).exists()
  
