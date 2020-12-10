from django import template
from django.conf import settings

register = template.Library()

import logging

logger = logging.getLogger(__name__)

register = template.Library()


@register.inclusion_tag('tom_targets/partials/target_data.html', takes_context=True)
def target_data(context, target):
    perms = context['perms']
    extras = {k['name']: target.extra_fields.get(k['name'], '') for k in settings.EXTRA_FIELDS if not k.get('hidden')}
    return {
        'perms': perms,
        'target': target,
        'extras': extras
    }


@register.inclusion_tag('tom_targets/partials/target_buttons.html', takes_context=True)
def target_buttons(context, target):
    perms = context['perms']
    return {
        'perms': perms,
        'target': target
    }
