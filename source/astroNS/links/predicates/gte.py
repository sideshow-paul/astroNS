""" Greater than or equal function """
import re

pattern = re.compile("(.*) >= (.*)")


def fn(groups, lsv_fn):
    """Greater than or equal to function"""
    field, value = groups
    return lambda data: float(lsv_fn(data, field)) >= float(value)
