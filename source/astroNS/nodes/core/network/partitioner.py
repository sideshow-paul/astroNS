# -*- coding: utf-8 -*-
from simpy.core import Environment
from typing import List, Dict, Tuple, Any, Optional, Callable

from nodes.core.base import BaseNode


class Partitioner(BaseNode):
    def __init__(self, env: Environment, name: str, configuration: Dict[str, Any]):
        """Initialize the node"""
        super().__init__(env, name, configuration, self.execute())
        self._num_messages: float = self.configuration.get("num_messages", 1)
        self._key: str = self.configuration.get("key", "KEY")
        # This is a list of text strings that contain the values to be compared
        self._time_delay: Callable[[], Optional[float]] = self.setFloatFromConfig(
            "time_delay", 0.00
        )

        self.env.process(self.run())

    @property
    def time_delay(self) -> Optional[float]:
        return self._time_delay()

    def execute(self):
        """The simpy execution loop"""
        delay: float = 0.0
        processing_time: float = delay
        data_out_list: List[Tuple] = []
        fields = []
        num_messages = 0
        while True:
            data_in = yield (delay, processing_time, data_out_list)

            if data_in:
                delay = self.time_delay
                processing_time = delay
                data_out_list = []
                for val in data_in[self._key]:
                    msg = data_in.copy()
                    msg[self._key] = val
                    data_out_list.append(msg)
            else:
                data_out_list = []
