"""
Nodes that perform network related functions.
"""

# Import the base node
msg_prefix = "    %|     0.00|2020-10-22T20:58:17.862886+00:00|      CelerNet     |[   Simulator   ]|00000000-0000-0000-000000000000|"

try:
    from .fiber_terminal import FiberTerminal

    print(msg_prefix + "Loaded FiberTerminal node.")
except ModuleNotFoundError as e:
    raise e
