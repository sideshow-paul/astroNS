

import pandas as pd
import pulsar
import json
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

class PulsarTopicSink(BaseNode):
    """ writes to topic and from a message from it"""

    def __init__(self, env: Environment, name: str, configuration: Dict[str, Any]):
        """Initialization"""
        self.delay: float = configuration.get("delay", 0.1)
        super().__init__(env, name, configuration, self.execute())
        self.pulsar_server: str = configuration.get("pulsar_server", "pulsar://localhost:6650")
        self.topic_name: str = configuration.get("topic_name", "sim_output")

        try:
            self.client = pulsar.Client(self.pulsar_server)
            self.producer = self.client.create_producer(self.topic_name)
            print(self.log_prefix() + f"Connected to Pulsar server at {self.pulsar_server}")
        except Exception as e:
            print(self.log_prefix() + f"Failed to connect to Pulsar: {str(e)}")

        self.env.process(self.run())

    def execute(self):
        """Execute function, part of simpy functionality"""
        delay_till_get_next_msg: float = self.delay
        time_to_send_data_out: float = 0.0
        data_in: Optional[Dict[str, Any]] = None
        data_out_list: List[Dict[str, Any]] = []

        while True:
            data_in = yield (delay_till_get_next_msg, time_to_send_data_out, data_out_list)

            try:
                # Process the incoming data
                data_out_list = [data_in]

                # Convert to JSON and send to Pulsar
                # might crash from the uuid
                # uuid's don't serialize
                data_in_copy: Dict[str, Any] = data_in.copy()
                data_in_copy['ID']           = str(data_in['ID'])
                data_in_copy['time']         = self.env.now_datetime().isoformat(timespec='microseconds')
                json_data_in: str            = json.dumps(data_in_copy)

                print(self.log_prefix(data_in_copy.get("ID", "unknown")) + f"Sending message to topic {self.topic_name}")
                self.producer.send(json_data_in.encode('utf-8'))

                # Yield back to simulation with no data (sink nodes don't produce output)
                time_to_send_data_out = 0.1
                delay_till_get_next_msg = 0.1

            except Exception as e:
                print(self.log_prefix() + f"Error processing message: {str(e)}")
                time_to_send_data_out = 0.0
                delay_till_get_next_msg = 0.0
                data_out_list = [data_in]
