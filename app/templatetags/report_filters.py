from django import template
import logging

logger = logging.getLogger(__name__)
register = template.Library()

@register.filter
def sum_attr(items, attr):
    """Sum a specific attribute across a list of dictionaries"""
    return sum(item[attr] for item in items)

@register.filter
def avg_attr(items, attr):
    """Calculate average of a specific attribute across a list of dictionaries"""
    if not items:
        return 0
    return sum(item[attr] for item in items) / len(items)

@register.filter
def max_attr(items, attr):
    """Get maximum value of a specific attribute across a list of dictionaries"""
    if not items:
        return 0
    return max(item[attr] for item in items)

@register.filter
def min_attr(items, attr):
    """Get minimum value of a specific attribute across a list of dictionaries"""
    if not items:
        return 0
    return min(item[attr] for item in items)

@register.filter
def percentage(value, total):
    """Calculate percentage"""
    try:
        return round((float(value) / float(total)) * 100, 1)
    except (ValueError, ZeroDivisionError):
        return 0

@register.filter(name='get_item', is_safe=True)
def get_item(dictionary, key):
    """Get item from dictionary by key, safely handling None cases"""
    logger.debug(f"get_item filter called with dictionary={dictionary} and key={key}")
    if dictionary is None:
        logger.debug("dictionary is None, returning None")
        return None
    try:
        key = str(key)
        result = dictionary.get(key)
        logger.debug(f"returning {result}")
        return result
    except (TypeError, ValueError) as e:
        logger.debug(f"error occurred: {e}")
        return None

@register.filter
def where(items, filter_string):
    """Filter items by key,value pair"""
    if not items:
        return []
    key, value = filter_string.split(',')
    return [item for item in items if str(item.get(key)) == value]
