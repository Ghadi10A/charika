from django import template

register = template.Library()

@register.filter
def get_comments(comments, post_id):
    return comments.get(post_id, [])
@register.filter
def star_unicode_to_char(value):
    try:
        star_char = chr(int(value, 16))
        return star_char
    except ValueError:
        return value