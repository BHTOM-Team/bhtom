from django import template
from django_comments.models import Comment
from tom_targets.models import Target

register = template.Library()


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
