"""
Nodes that perform network related functions.
"""

# Import the base node
msg_prefix = "    %|     0.00|0000-00-00T00:00:00.000000+00:00|      astroNS     |[   Simulator   ]|00000000-0000-0000-000000000000|"

try:
    from .fiber_terminal import FiberTerminal

    print(msg_prefix + "Loaded FiberTerminal node.")
except ModuleNotFoundError as e:
    raise e
