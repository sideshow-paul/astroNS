msg_prefix = "    %|     0.00|2020-10-22T20:58:17.862886+00:00|      astroNS     |[   Simulator   ]|00000000-0000-0000-000000000000|"
try:
    from .LLM_scenario import LLMScenario

    print(msg_prefix + "Loaded LLM_scenario node.")
except ModuleNotFoundError as e:
    raise e
