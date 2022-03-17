""" Does not equal """
import re

pattern = re.compile("(.*) != (.*)")


def fn(groups, lsv_fn):
    """Does not equal function"""
    field, value = groups
    try:
        float_value = float(value)
        return lambda data: float(lsv_fn(data, field)) != float_value
    except:
        # assume a string
        return lambda data: lsv_fn(data, field) != value
