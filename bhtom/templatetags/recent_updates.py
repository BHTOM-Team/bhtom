from django import template
from django_comments.models import Comment
from guardian.shortcuts import get_objects_for_user
from tom_targets.models import Target
from astropy.time import Time


register = template.Library()


@register.inclusion_tag('tom_targets/partials/recent_targets.html', takes_context=True)
def recent_targets(context, limit=10):
    """
    Displays a list of the most recently created targets in the TOM up to the given limit, or 10 if not specified.
    """
    user = context['request'].user

    target_query = get_objects_for_user(user, 'tom_targets.view_target').filter(['targetextra__key', 'jdlastobs']).order_by('-targetextra__value')[:limit]

    targets = []

    for target in target_query:
        jdlastobs = target.extra_fields.get('jdlastobs')
        if jdlastobs:
            lastobs = Time(jdlastobs, format='jd')
            targets.append({'target': target, 'jdlastobs': lastobs.to_datetime()})
        else:
            targets.append({'target': target})

    return {'targets': targets}


@register.inclusion_tag('comments/list.html')
def recent_comments_with_targets(limit=5):
    """
    Displays a list of the most recent comments in the TOM up to the given limit, or 10 if not specified.
    """
    with_targets = []
    for comment in Comment.objects.all().order_by('-submit_date')[:limit]:
        try:
            target: Target = Target.objects.get(pk=comment.object_pk)
        except Target.DoesNotExist:
            continue
        if target:
            with_targets.append({'target': target,
                                 'comment': comment})
    return {'comment_list': with_targets}
