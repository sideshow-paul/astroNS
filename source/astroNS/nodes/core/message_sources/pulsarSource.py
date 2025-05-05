

import pandas as pd
import pulsar
import json.tool
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

class PulsarTopicSource(BaseNode):
    """ Reads from a source topic and creates a message from it"""

    def __init__(self, env: Environment, name: str, configuration: Dict[str, Any]):
        """Initialization"""
        super().__init__(env, name, configuration, self.execute())
        self.pulsar_server: str = configuration.get("pulsar_server", "pulsar://localhost:6650")
        self.topic_name: str = configuration.get("topic_name", "my-topic")
        self.subscription_name: str = configuration.get("sub_name", "my-sub")
        self.simtime_field_name: str = configuration.get("simtime_field_name", "simtime")

        self.client = pulsar.Client(self.pulsar_server)
        self.consumer = self.client.subscribe(self.topic_name, subscription_name=self.subscription_name)

        self.env.process(self.run())

    def execute(self):
        """Execute function, part of simpy functionality"""
        yield 0.0, 0.0, []

        while True:
            msg = self.consumer.receive()
            
            self.consumer.acknowledge(msg)

            message = msg.data().decode('utf-8')

            parsed_message = json.loads(message)
            id: str = str(uuid.uuid4())
            parsed_message['ID'] = id
            parsed_message[self.msg_size_key] = 10
            parsed_message['simtime_arrived'] = self.env.now
            print(self.log_prefix(parsed_message['ID']) + "Received message: {message}")
            #import pudb; pu.db
            simtime_of_msg = parsed_message.get(self.simtime_field_name, self.env.now)
            delay = simtime_of_msg - self.env.now
            yield delay, 0.0, [parsed_message]





