"""
Aerospace-related nodes.
"""

# Import all aerospace nodes
msg_prefix = "    %|     0.00|2020-10-22T20:58:17.862886+00:00|      astroNS     |[   Simulator   ]|00000000-0000-0000-000000000000|"
try:
    from .access import Access

    print(msg_prefix + "Loaded Access node.")
except ModuleNotFoundError as e:
    raise e

# try:
#     from .propagator import Propagator

#     print(msg_prefix + "Loaded Propagator node.")
# except ModuleNotFoundError as e:
#     raise e
