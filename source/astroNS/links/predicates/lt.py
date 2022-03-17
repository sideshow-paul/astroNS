""" Less than function """
import re

pattern = re.compile("(.*) < (.*)")


def fn(groups, lsv_fn):
    """Less than function"""
    field, value = groups
    return lambda data: float(lsv_fn(data, field)) < float(value)
