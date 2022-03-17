""" Find if key is missing """
import re

pattern = re.compile("(.*) MISSING")


def fn(groups, lsv_fn):
    """Key is missing function"""
    field = groups[0]
    if field == "SimTime":
        return lambda data: False
    else:
        return lambda data: not field in data[1]
