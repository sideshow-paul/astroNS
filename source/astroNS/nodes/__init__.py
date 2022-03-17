"""
Nodes operate on messages by affecting either the message state, the node state
or both.
"""
# Import the base node
msg_prefix = "    %|    0.00|2020-10-22T20:58:17.862886+00:00|      CelerNet     |[   Simulator   ]|00000000-0000-0000-000000000000|"
try:
    from nodes.core.meta import MetaNode

    print(msg_prefix + "Loaded MetaNode node.")
except Exception as e:
    print(e)
    raise ModuleNotFoundError("Metanode is a required node for operation.")

from nodes.core.base import BaseNode

# Import all core nodes
from .core import *
from .aerospace import *
from .network import *
