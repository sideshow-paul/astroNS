"""
Pydantic models and related nodes for astroNS.
"""

# Import all pydantic models and nodes
msg_prefix = "    %|     0.00|2020-10-22T20:58:17.862886+00:00|      astroNS     |[   Simulator   ]|00000000-0000-0000-000000000000|"

# try:
#     from .simulator_interfaces import TaskAssignment, SimulatorControlMessage, CollectedTargetData

#     print(msg_prefix + "Loaded Pydantic models: TaskAssignment, SimulatorControlMessage, CollectedTargetData.")
# except ModuleNotFoundError as e:
#     raise e

try:
    from .ParseJsonMessage import ParseJsonMessage

    print(msg_prefix + "Loaded ParseJsonMessage node.")
except ModuleNotFoundError as e:
    raise e
