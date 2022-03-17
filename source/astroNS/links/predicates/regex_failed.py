""" Regular expression failed to find match """
import re

pattern = re.compile("(.*) failed_reg '(.*)'")


def fn(groups, lsv_fn):
    """Regular expression did not contain a match"""
    field, pattern = groups
    route_regex = re.compile(pattern)
    return lambda data: route_regex.search(str(lsv_fn(data, field))) == None
