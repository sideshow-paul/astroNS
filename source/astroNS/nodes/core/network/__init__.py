"""
Network nodes perform many of the base functions for astroNS.
"""
# Import nodes
msg_prefix = "    %|     0.00|2020-10-22T20:58:17.862886+00:00|      astroNS     |[   Simulator   ]|00000000-0000-0000-000000000000|"
try:
    from .delaytime import DelayTime

    print(msg_prefix + "Loaded DelayTime node.")
except ModuleNotFoundError as e:
    raise e

try:
    from .and_gate import AndGate

    print(msg_prefix + "Loaded AndGate node.")
except ModuleNotFoundError as e:
    raise e

try:
    from .keydelaytime import KeyDelayTime

    print(msg_prefix + "Loaded KeyDelayTime node.")
except ModuleNotFoundError as e:
    raise

try:
    from .combiner import Combiner

    print(msg_prefix + "Loaded Combiner node.")
except ModuleNotFoundError as e:
    raise e

try:
    from .partitioner import Partitioner

    print(msg_prefix + "Loaded Partitioner node.")
except ModuleNotFoundError as e:
    raise e

try:
    from .minimizer import Minimizer

    print(msg_prefix + "Loaded Minimizer node.")
except ModuleNotFoundError as e:
    raise e

try:
    from .maximizer import Maximizer

    print(msg_prefix + "Loaded Maximizer node.")
except ModuleNotFoundError as e:
    raise e

try:
    from .processor import Processor

    print(msg_prefix + "Loaded Processor node.")
except ModuleNotFoundError as e:
    raise e

try:
    from .delaysize import DelaySize

    print(msg_prefix + "Loaded DelaySize node.")
except ModuleNotFoundError as e:
    raise e
