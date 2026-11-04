from django import template

from library.review_navigation import navigation

register = template.Library()


@register.simple_tag(takes_context=True)
def reviewer_navigation(context):
    return navigation(context["request"], context)
