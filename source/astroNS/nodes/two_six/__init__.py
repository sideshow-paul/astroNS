


msg_prefix = "    %|     0.00|0000-00-00T00:00:00.000000+00:00|      astroNS     |[   Simulator   ]|00000000-0000-0000-000000000000|"


try:
    from .UnwrapPayload import UnwrapPayload
    from .ProcessBatchPayload import ProcessBatchPayload
    from .ProcessSimTimeAdvanceCommandPayload import ProcessSimTimeAdvanceCommandPayload
    from .ProcessSimulationResetPayload import ProcessSimulationResetPayload
    from .WrapPayload import WrapPayload

    print(msg_prefix + "Loaded UnwrapPayload node.")
    print(msg_prefix + "Loaded WrapPayload node.")

    print(msg_prefix + "Loaded ProcessBatchPayload node.")
    print(msg_prefix + "Loaded ProcessSimTimeAdvanceCommandPayload node.")
    print(msg_prefix + "Loaded ProcessSimulationResetPayload node.")
except ModuleNotFoundError as e:
    raise e
