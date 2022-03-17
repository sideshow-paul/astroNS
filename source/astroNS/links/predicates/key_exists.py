""" Find if key exists """
import re

pattern = re.compile("(.*) EXISTS")


def fn(groups, lsv_fn):
    """If the key exists function"""
    field = groups[0]
    if field == "SimTime":
        return lambda data: True
    else:
        return lambda data: field in data[1]
