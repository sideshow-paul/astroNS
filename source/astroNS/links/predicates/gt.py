""" This attaches a greater than function lambda expression to the link.

Nothing is executed inside this function, it exists only to provide a function
that is used later on.

"""
import re

pattern = re.compile("(.*) > (.*)")


def fn(groups, lsv_fn):
    """Greater than function"""
    field, value = groups
    return lambda data: float(lsv_fn(data, field)) > float(value)
