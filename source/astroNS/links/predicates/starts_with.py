""" Find if key starts with """
import re

pattern = re.compile("(.*) starts_with (.*)")


def fn(groups, lsv_fn):
    """Starts with function"""
    field, value = groups
    return lambda data: str(lsv_fn(data, field)).startswith(value)
