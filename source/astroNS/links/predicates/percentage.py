""" Percentage function, only works with random_router_value! """
import re

pattern = re.compile("(.*) <=> (.*)")


def fn(groups, lsv_fn):
    """Percent function"""
    start, end = groups
    # assumes the routing code inserts a 'random_router_value' key value(int)
    return lambda data: data[1]["random_router_value"] >= int(start) and data[1][
        "random_router_value"
    ] <= int(end)
