"""
Random Data Source Node -- Generates messages to pulse through the system.
"""
import random
import uuid

rd = random.Random()
rd.seed(0)
uuid.uuid4 = lambda: uuid.UUID(int=rd.getrandbits(128))

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


class RandomDataSource(BaseNode):
    """A message source that sends randomized messages."""

    def __init__(self, env: Environment, name: str, configuration: Dict[str, Any]):
        """Initialization"""
        super().__init__(env, name, configuration, self.execute())
        self._random_size_min: Callable[[], Optional[float]] = self.setIntFromConfig(
            "random_size_min", 10
        )
        self._random_size_max: Callable[[], Optional[float]] = self.setIntFromConfig(
            "random_size_max", 100
        )
        self._random_delay_min: Callable[[], Optional[float]] = self.setFloatFromConfig(
            "random_delay_min", 1.0
        )
        self._random_delay_max: Callable[[], Optional[float]] = self.setFloatFromConfig(
            "random_delay_max", 10.0
        )

        self._single_pulse: Callable[[], Optional[bool]] = self.setBoolFromConfig(
            "single_pulse", False
        )

        self._start_node_active: Callable[[], Optional[bool]] = self.setBoolFromConfig(
            "start_node_active", True
        )

        self._active = self._start_node_active()

        self.env.process(self.run())

    @property
    def random_size_min(self):
        """Minimum value to generate a message size
        :param random_size_min: Minimum size
        :return: integer
        """
        return int(self._random_size_min())

    @property
    def random_size_max(self):
        """Maximum value to generate a message size
        :param random_size_max: Maximum size
        :return: integer
        """
        return int(self._random_size_max())

    @property
    def random_delay_min(self) -> Optional[float]:
        """Minimum value to generate a message delay
        :param random_delay_min: Minimum size
        :return: float
        """
        return self._random_delay_min()

    @property
    def random_delay_max(self) -> Optional[float]:
        """Maximum value to generate a message delay
        :param random_delay_max: Maximum size
        :return: float
        """
        return self._random_delay_max()

    @property
    def single_pulse(self) -> Optional[bool]:
        """Determine whether to send continuous or single pulse messages.
        :param single_pulse: True or False
        :return: Bool
        """
        return self._single_pulse()

    @property
    def start_node_active(self) -> Optional[bool]:
        """Determine whether the node starts active or not.
        :param start_node_active: True or False
        :return: Bool
        """
        return self._start_node_active()

    ## Other node functions

    def active(self) -> bool:
        return self._active

    def set_node_inactive(self):
        self._active = False

    ## Main execution function

    def execute(self):
        """Execute function, part of simpy functionality"""
        # Do this first, one time
        yield 0.0, 0.0, []

        if self.active():
            delay = 0.0
            processing_time = random.uniform(
                self.random_delay_min, self.random_delay_max
            )

            # Send first message
            id: str = str(uuid.uuid4())
            data_list: List[Dict[str, Any]] = [
                {
                    "ID": id,
                    self.msg_size_key: random.randint(
                        self.random_size_min, self.random_size_max
                    ),
                }
            ]

            # Log the message
            print(
                self.log_prefix(id)
                + "Random Data Msg # |{}| sent. Cooling down |{:f}| SimSeconds".format(
                    data_list[0], processing_time
                )
            )

            if self.single_pulse:
                self.set_node_inactive()

            # Send the message immediately
            yield 0, 0, data_list

        # After the first time do this
        while True:
            delay = 0

            if self.active():
                # Create a message
                id: str = str(uuid.uuid4())
                data_list: List[Dict[str, Any]] = [
                    {
                        "ID": id,
                        self.msg_size_key: random.randint(
                            self.random_size_min, self.random_size_max
                        ),
                    }
                ]

                processing_time = random.uniform(
                    self.random_delay_min, self.random_delay_max
                )

                # Log the message
                print(
                    self.log_prefix(id)
                    + "Random Data Msg # |{}| sent. Cooling down |{:f}| SimSeconds".format(
                        data_list[0], processing_time
                    )
                )

                yield processing_time, delay + processing_time, data_list
