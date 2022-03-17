# -*- coding: utf-8 -*-
"""And Gate Node blocks messages until conditions are accepted.

The AndGateNode is an extension of the original astroNS GateNode. It works by
allowing the first message that satisfies all of the conditions through. It
works similar to all predicates (:func:`~astroNS.links.predicates`). As a
message (functionally, a dictionary) hits the node, each key will be checked
as a condition. If any of the keys changes a variable it will be stored and
updated in the node. It does not require a single message that matches all 
conditions. Each condition can be satisfied by a single message or multiple
to build up the correct condition. 

If a message hits the node and the gate is not open the default behavior will
refuse the message and it will stop. By setting a configuration, the messages
will be stored and released once the gate condition(s) is satisfied.

"""
from simpy.core import Environment
from typing import List, Dict, Tuple, Any, Optional, Callable

from nodes.core.base import BaseNode
from links.predicates import patterns
from common.left_side_value import left_side_value


class AndGate(BaseNode):
    """AndGate Node class

    ::
        Maneuver_Planned:
            type: AddKeyValue
            key: Maneuver_Planned
            value: "True"
            Maneuver_Decision: ~
        Maneuver_Decision:
            type: AndGate
            conditions:
                - "SimTime > 100"
                - "Maneuver_Planned == True"
            Xmit_Load_to_UL: ~

    The sample above will attach a Manuever_Planned key with value "True". This would
    allow any messages that come through from the Manuever_Planned node after SimTime
    of 100

    """

    def __init__(self, env: Environment, name: str, configuration: Dict[str, Any]):
        """Initialize the node"""
        super().__init__(env, name, configuration, self.execute())

        ### Node Variables
        self._conditions: list = self.configuration.get("conditions", [])
        # This is a list of text strings that contain the values to be compared
        self._time_delay: Callable[[], Optional[float]] = self.setFloatFromConfig(
            "time_delay", 0.00
        )
        self._processing_delay: Callable[[], Optional[float]] = self.setFloatFromConfig(
            "processing_delay", 0.00
        )
        self._drop_blocked_messages: Callable[
            [], Optional[bool]
        ] = self.setBoolFromConfig("drop_blocked_messages", True)
        self._blocked_message_FIFO: Callable[
            [], Optional[bool]
        ] = self.setBoolFromConfig("blocked_messages_FIFO", True)

        ### Internal Values
        self.gate_values = [None] * len(self._conditions)
        self.gate_open: bool = False

        self.env.process(self.run())

    @property
    def conditions(self):
        """A list of parameters that must be satisfied to allow messages to
        flow through the gate.

        Sample
        ::
            Collect_Decision:
                type: AndGate
                conditions:
                    - "SimTime >= 10.5"
                    - "Uplink_Planned == True"
                    - "Schedule EXISTS"
                Xmit_Load_to_UL: ~

        The sample requires three conditions to be allowed through. It shows
        that different predicates are accepted.

        """
        return self._conditions

    @property
    def time_delay(self) -> Optional[float]:
        """Set the delay time property

        Sample
        ::
            Collect_Decision:
                type: AndGate
                time_delay: 30
                conditions:
                    - "SimTime >= 10.5"
                    - "Uplink_Planned == True"
                    - "Schedule EXISTS"
                Xmit_Load_to_UL: ~

        The sample requires three conditions but will also delay the message
        30 units.

        """
        return self._time_delay()

    @property
    def processing_delay(self) -> Optional[float]:
        """Set the processing delay or node blocking property

        Sample
        ::
            Collect_Decision:
                type: AndGate
                processing_delay: 30
                conditions:
                    - "SimTime >= 10.5"
                    - "Uplink_Planned == True"
                    - "Schedule EXISTS"
                Xmit_Load_to_UL: ~

        The sample requires three conditions but will also block the node from
        processing additional messages for 30 units. In this case the node will
        also queue messages and send them if the gate is opened.

        """
        return self._processing_delay()

    @property
    def drop_blocked_messages(self) -> Optional[float]:
        """Set the option to store messages and send them after the gate is
        opened.

        Sample
        ::
            Collect_Decision:
                type: AndGate
                drop_blocked_messages: False
                conditions:
                    - "SimTime >= 10.5"
                    - "Uplink_Planned == True"
                    - "Schedule EXISTS"
                Xmit_Load_to_UL: ~

        The sample requires three conditions and will store messages that
        arrive while the gate is closed. Once the gate is opened, the messages
        will be sent in a First In, First Out schema.

        """
        return self._drop_blocked_messages()

    @property
    def blocked_messages_FIFO(self) -> Optional[float]:
        """Set the option to store messages and send them after the gate is
        opened. This variable is conditional on drop_blocked_messages to be set
        to False, because without it, no messages are stored within the node.

        Sample
        ::
            Collect_Decision:
                type: AndGate
                drop_blocked_messages: False
                blocked_messages_FIFO: False
                conditions:
                    - "SimTime >= 10.5"
                    - "Uplink_Planned == True"
                    - "Schedule EXISTS"
                Xmit_Load_to_UL: ~

        The sample requires three conditions and will store messages that
        arrive while the gate is closed. However, this sample requests that
        messages be sent out in Last In, First Out order.

        """
        return self._drop_blocked_messages()

    def execute(self):
        """The simpy execution loop"""
        delay: float = 0.0
        processing_time: float = 0.0
        data_out_list: List[Tuple] = []

        stored_messages: List[Tuple] = []

        while True:
            data_in = yield (processing_time, processing_time + delay, data_out_list)

            if data_in:
                # Set the message delay times.
                delay = self.time_delay
                processing_time = self.processing_delay

                # Check for updates to the conditions
                for key, condition in enumerate(self._conditions):
                    # For each condition
                    for pattern, fn in patterns:
                        # Check if the pattern matches
                        match_result = pattern.search(condition)
                        if match_result:
                            # The pattern matches
                            field, value = match_result.groups()
                            break
                    else:
                        # Hits if break was never found.
                        raise AttributeError("The pattern could not be matched.")

                    if field in data_in:
                        if fn(match_result.groups(), left_side_value)(
                            [self.env.now, data_in]
                        ):
                            self.gate_values[key] = True
                        else:
                            self.gate_values[key] = False
                    else:
                        # The field didn't exist, do nothing
                        pass

                # Check if gate is open/closed
                if all(self.gate_values):
                    # All gates are open, send through.
                    if self.drop_blocked_messages:
                        print(
                            "{} Gates are open, all messages will flow through node.".format(
                                self.log_prefix(data_in["ID"])
                            )
                        )
                        data_out_list = [data_in.copy()]
                        # No stored messages to send.
                    else:
                        print(
                            "{} Gates are open, all stored messages will flow through node.".format(
                                self.log_prefix(data_in["ID"])
                            )
                        )

                        # Combine this message with all stored messages.
                        data_out_list = [data_in.copy()]
                        data_out_list.extend(stored_messages)
                        data_out_list = sorted(
                            data_out_list,
                            key=lambda i: i.get("time_sent", 0),
                            reverse=not self.blocked_messages_FIFO,
                        )
                else:
                    # Gates are closed, determine if storage is needed.
                    if self.drop_blocked_messages == False:
                        print(
                            "{} Gates are closed, message stored.".format(
                                self.log_prefix(data_in["ID"])
                            )
                        )
                        stored_messages.extend([data_in.copy()])
                    else:
                        # Gate is closed, message is dropped.
                        print(
                            "{} Gates are closed, message dropped.".format(
                                self.log_prefix(data_in["ID"])
                            )
                        )
                        data_out_list = []
            else:
                data_out_list = []
