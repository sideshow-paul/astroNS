"""
Subnodes look like nodes, but will return a value to be substituted into
another node.
"""
# Import nodes
msg_prefix = "    %|    0.00|2020-10-22T20:58:17.862886+00:00|      CelerNet     |[   Simulator   ]|00000000-0000-0000-000000000000|"
try:
    from .randomdistrib import RandomDistrib

    print(msg_prefix + "Loaded RandomDistrib node.")
except ModuleNotFoundError as e:
    raise e
