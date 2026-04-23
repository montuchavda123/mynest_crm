from django import template

register = template.Library()

@register.filter(name='get_dict_value')
def get_dict_value(dictionary, key):
    if dictionary is None:
        return ""
    return dictionary.get(key, "")
