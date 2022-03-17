"""
Fiber terminal creates a fiber connection between nodes. 

It must be connected to two fiber nodes in order. The first node will include
it's position in the message to the second. This key will be used on the
second node to calculate the latency.
"""

import uuid

from simpy.core import Environment
from astropy.constants import c
import astropy.units as u
from geopy.distance import geodesic

from nodes.core.base import BaseNode

from typing import (
    List,
    Dict,
    Tuple,
    Any,
    Iterator,
    Optional,
    Type,
    Callable,
    Generator,
    Iterable,
    Union as typeUnion,
)


class FiberTerminal(BaseNode):
    """A message source that sends messages with its current location."""

    def __init__(self, env: Environment, name: str, configuration: Dict[str, Any]):
        """Initialization"""
        super().__init__(env, name, configuration, self.execute())
        self._efficiency = configuration.get("efficiency", 0.95)
        self._refractive_index = configuration.get("refractive_index", 1.47)

        self.env.process(self.run())

    @property
    def efficiency(self):
        """Efficiency of cabling between two nodes, used to artifically inflate
        the actual distance the fiber optic cable
        :param efficiency: Cabling efficiency, a value of 1 would mean that the
        cable flows directly between the two nodes with no deviations

        :return: float
        """
        return float(self._efficiency)

    @property
    def refractive_index(self):
        """Refractive index is the slowdown of the speed of light through the
        fiber material compared to free space
        :param refractive_index: Refractive index of fiber material to slow
        down speed of light
        :return: float
        """
        return float(self._refractive_index)

    def execute(self):
        """Execute function, part of simpy functionality"""
        delay: float = 0.0
        processing_time: float = delay
        data_out_list: List[Tuple] = []
        while True:
            data_in = yield (delay, processing_time, data_out_list)

            if data_in:
                msg = data_in.copy()
                if "fiber_transmit_location" in msg:
                    # Calculate the delay
                    try:
                        rcvr_position = self.get_location(self.env.now)[0][:2]
                    except AttributeError:
                        raise AttributeError("No Propagator was attached.")
                    trans_position = msg["fiber_transmit_location"][0][:2]
                    # print(rcvr_position, trans_position)
                    d = geodesic(rcvr_position, trans_position).km
                    v = c.to(u.km / u.s).value / self._refractive_index
                    t = (d / self._efficiency) / v
                    print(
                        self.log_prefix(id)
                        + "Receiving at fiber location -- Message delay was {}".format(
                            t
                        )
                    )
                    msg.pop("fiber_transmit_location")
                    delay = t
                    processing_time = t
                    data_out_list = [msg]
                else:
                    # Add the transmit location to the message
                    msg["fiber_transmit_location"] = self.get_location(self.env.now)
                    print(
                        self.log_prefix(id)
                        + "Transmitting from Fiber Location -- {}".format(
                            msg["fiber_transmit_location"]
                        )
                    )
                    delay = 0
                    processing_time = 0
                    data_out_list = [msg]
