""" Message Sources generate messages to stimulate the network

"""
msg_prefix = "    %|     0.00|2020-10-22T20:58:17.862886+00:00|      CelerNet     |[   Simulator   ]|00000000-0000-0000-000000000000|"
try:
    from .random_data_source import RandomDataSource

    print(msg_prefix + "Loaded RandomDistrib node.")
except ModuleNotFoundError as e:
    raise e

try:
    from .add_key_value import AddKeyValue

    print(msg_prefix + "Loaded AddKeyValue node.")
except ModuleNotFoundError as e:
    raise e

try:
    from .position_report import PositionReport

    print(msg_prefix + "Loaded PositionReport node.")
except ModuleNotFoundError as e:
    raise e

try:
    from .file_data_source import FileDataSource

    print(msg_prefix + "Loaded FileDataSource node.")
except ModuleNotFoundError as e:
    raise e

try:
    from .pulsarSource import PulsarTopicSource
    print(msg_prefix + "Loaded PulsarTopicSource node.")

except ModuleNotFoundError as e:
    raise e