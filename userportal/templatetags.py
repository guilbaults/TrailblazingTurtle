from django import template
from userportal.common import anonymize as a

register = template.Library()


@register.filter
def anonymize(name):
    return a(name)
