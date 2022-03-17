""" Regular expression match """
import re

pattern = re.compile("(.*) regex '(.*)'")


def fn(groups, lsv_fn):
    """Regular expression search function"""
    field, pattern = groups
    route_regex = re.compile(pattern)
    return lambda data: route_regex.search(str(lsv_fn(data, field))) != None
