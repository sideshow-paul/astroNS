
msg_prefix = "    %|     0.00|2020-10-22T20:58:17.862886+00:00|      astroNS     |[   Simulator   ]|00000000-0000-0000-000000000000|"
try:
    from .pulsarSink import PulsarTopicSink

    print(msg_prefix + "Loaded PulsarTopicSink node.")
except ModuleNotFoundError as e:
    raise e

try:
    from .mathis_sink import MathisSink

    print(msg_prefix + "Loaded MathisSink node.")
except ModuleNotFoundError as e:
    print(msg_prefix + f"Failed to load MathisSink node: {e}")