# -*- coding: utf-8 -*-
"""Combiner node combines messages until a number of messages have been received.

The Combiner node will wait until a pre-defined number of messages have been
sent to the node. Once that message is received, the last received message is
sent, with all prior messages dropped. The message is updated with a list
representing the combined values of all messages that have a set key in it.

This node might be useful if you would like to combine all file sizes of each
message received into a list. Or you might want to combine a list of time to
next satellite access, etc. The input can be either a list, int/float, or 
string. By leaving the default, this can also convert a float or string into a
list for usage somewhere else.

"""
from simpy.core import Environment
from typing import List, Dict, Tuple, Any, Optional, Callable

from nodes.core.base import BaseNode
from links.predicates import patterns
from common.left_side_value import left_side_value


class Combiner(BaseNode):
    def __init__(self, env: Environment, name: str, configuration: Dict[str, Any]):
        """Initialize the node"""
        super().__init__(env, name, configuration, self.execute())
        self._num_messages: float = lambda: self.configuration.get("num_messages", 1)
        self._key: str = lambda: self.configuration.get("key", self.msg_size_key)
        # This is a list of text strings that contain the values to be compared
        self._time_delay: Callable[[], Optional[float]] = self.setFloatFromConfig(
            "time_delay", 0.00
        )
        self._processing_delay: Callable[[], Optional[float]] = self.setFloatFromConfig(
            "processing_delay", 0.00
        )

        self.env.process(self.run())

    @property
    def time_delay(self) -> Optional[float]:
        """Set the delay time property

        Sample
        ::
            Collect_Decision:
                type: Combiner
                time_delay: 30
                num_messages: 5

        This waits until 5 messages are received and delays a single message 30
        units. The node may send out an additional message immediately if 5
        additional messages arrive The combined message has a list of file
        sizes for the 5 messages.

        """
        return self._time_delay()

    @property
    def processing_delay(self) -> Optional[float]:
        """Set the processing time property

        Sample
        ::
            Collect_Decision:
                type: Combiner
                processing_delay: 30
                num_messages: 5

        This waits until 5 messages are received and can only send a grouped
        message at a minimum of 30 units The combined message has a list of file
        sizes for the 5 messages.

        """
        return self._processing_delay()

    @property
    def key(self) -> Optional[str]:
        """Set the key to combine

        Sample
        ::
            Collect_File_Sizes:
                type: Combiner
                key: size_mbits
                num_messages: 20

        This will combine the file sizes of 20 messages.
        """
        return self._key()

    @property
    def num_messages(self) -> Optional[float]:
        """Set the number of messages property

        Sample
        ::
            Collect_Decision:
                type: Combiner
                num_messages: 30

        This will collect 30 messages into one message, using the default for
        the key to combine, which is the file size.

        """
        return self._num_messages()

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
                processing_time = self.processing_delay
                delay = self.time_delay + self.processing_delay
                num_messages += 1

                # Add to the combined list
                try:
                    if type(data_in[self.key]) == type(list()):
                        fields.extend(data_in[self.key])
                    else:
                        fields.extend([data_in[self.key]])

                    print(
                        "{} Added {} to key: {}.".format(
                            self.log_prefix(data_in["ID"]),
                            data_in[self._key],
                            self._key,
                        )
                    )
                except:
                    print(
                        "{} Key {} not found in message, not added to list.".format(
                            self.log_prefix(data_in["ID"]), self.key
                        )
                    )

                # Check if combined message can go out.
                if num_messages >= self.num_messages:
                    print(
                        "{} Total threshold messages met, forwarding combined message.".format(
                            self.log_prefix(data_in["ID"])
                        )
                    )
                    data_out = data_in.copy()
                    data_out[self.key] = fields
                    # print(fields)
                    data_out_list = [data_out]
                    ##### Clean up #####
                    num_messages = 0
                    fields = []
                else:
                    data_out_list = []

            else:
                data_out_list = []
