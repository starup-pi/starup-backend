from django import template

register = template.Library()


@register.filter(name='get_attr')
def get_attr(obj, field_name):
    """
    Retorna o valor de `field_name` em `obj`, usando `get_<field>_display()`
    quando o campo é um ENUM (TextChoices), para exibir o rótulo legível.
    """
    display_method = getattr(obj, f'get_{field_name}_display', None)
    if callable(display_method):
        try:
            return display_method()
        except Exception:
            pass
    return getattr(obj, field_name, '')
