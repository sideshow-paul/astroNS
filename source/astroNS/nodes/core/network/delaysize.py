"""
Delay Size is a node that calculates how long it takes to transmit a message based on its file size.
"""

from nodes.core.base import BaseNode
from simpy.core import Environment

from typing import Dict, List, Tuple, Any, Callable, Optional, Union as typeUnion


class DelaySize(BaseNode):
    """DelaySize is a delay time node that calculates the delay before sending a message based on the message size."""

    def __init__(self, env: Environment, name: str, configuration: Dict[str, Any]):
        super().__init__(env, name, configuration, self.execute())
        self._rate_per_mbit: Callable[[], Optional[float]] = self.setFloatFromConfig(
            "rate_per_mbit", 100.0
        )
        self.env.process(self.run())

    @property
    def rate_per_mbit(self) -> Optional[float]:
        """Processing rate per Mbit"""
        return self._rate_per_mbit()

    # @coroutineSend
    def execute(self):
        """Execute function for the DelaySize node"""
        delay: float = 0.0
        processing_time: float = 0.0
        data_in: Dict[str, Any]

        data_out_list: List[Dict[str, Any]] = []
        while True:
            data_in = yield (delay, processing_time, data_out_list)
            # import pudb; pu.db
            if data_in:
                # The delay is what is set by the size of the message
                delay = data_in[self.msg_size_key] / self.rate_per_mbit
                # Add the time to the total processing on this node
                processing_time = delay
                # Make a copy of the data at this time
                data_out_list = [data_in.copy()]
                print(
                    self.log_prefix(data_in["ID"])
                    + "Data size of |%d| arrived at |%f|. Processing took |%f| simtime units"
                    % (data_in[self.msg_size_key], self.env.now, delay)
                )
            else:
                data_out_list = []
