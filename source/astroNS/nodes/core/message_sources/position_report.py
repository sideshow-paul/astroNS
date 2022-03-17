"""
Position report provides information regarding the position of a metanode.
"""

import uuid

from simpy.core import Environment

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


class PositionReport(BaseNode):
    """A message source that sends messages with its current location."""

    def __init__(self, env: Environment, name: str, configuration: Dict[str, Any]):
        """Initialization"""
        super().__init__(env, name, configuration, self.execute())
        self._frequency = configuration.get("frequency", 10)

        self.env.process(self.run())

    @property
    def frequency(self):
        """Frequency to send position data
        :param frequency: Frequency updates
        :return: integer
        """
        return int(self._frequency)

    def execute(self):
        """Execute function, part of simpy functionality"""
        # this yield is needed to prime the generator, it is ignored by the engine
        yield 0.0, 0.0, []

        while True:
            delay: int = self._frequency
            # Pretend to Read data from source, one line at a time
            id: str = uuid.uuid4()
            if self.meta_node is not None:
                data_list: List[Dict[str, Any]] = [
                    {
                        "ID": id,
                        "size_mbits": 0,
                        "position": self.get_location(self.env.now),
                    }
                ]
                print(
                    self.log_prefix(id)
                    + "Position -- {}".format(data_list[0]["position"])
                )
                yield delay, delay, data_list
