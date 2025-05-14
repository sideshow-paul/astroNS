

import pandas as pd
import pulsar
import json
import uuid
import simpy

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
        #super().__init__(env, name, configuration, self.execute())
        self.pulsar_server: str = configuration.get("pulsar_server", "pulsar://localhost:6650")
        self.topic_name: str = configuration.get("topic_name", "my-topic")
        self.subscription_name: str = configuration.get("sub_name", "my-sub")
        self.simtime_field_name: str = configuration.get("simtime_field_name", "simtime")
        self.poll_frequency_secs: float = configuration.get("poll_frequency_secs", 10.0)
        self.generates_data_only: bool = True

        self.client = pulsar.Client(self.pulsar_server)
        self.consumer = self.client.subscribe(self.topic_name,
                                              subscription_name=self.subscription_name)#,
                                              #message_listener=self.message_listener
                                              #receiver_queue_size=1)
        super().__init__(env, name, configuration, self.execute())

        self.env.process(self.run())
    def message_listener(self, consumer, msg):
            """Callback function for handling incoming messages asynchronously"""
            import pudb; pu.db
            try:

                message = msg.data().decode('utf-8')
                try:
                    parsed_message = json.loads(message)
                    id: str = str(uuid.uuid4())
                    parsed_message['ID'] = id
                    parsed_message[self.msg_size_key] = 10
                    parsed_message['simtime_arrived'] = self.env.now
                    print(self.log_prefix(parsed_message['ID']) + f"Received message: {message}")

                    simtime_of_msg = parsed_message.get(self.simtime_field_name, self.env.now)
                    delay = max(simtime_of_msg - self.env.now, 0)
                    print(self.log_prefix(parsed_message['ID']) + f"Delay: {delay}")
                except json.JSONDecodeError as e:
                    print(self.log_prefix() + f"Error parsing JSON message: {e}")
                    print(self.log_prefix() + f"Raw message content: {message}")
                    return

                # Send data to output with appropriate delay
                simpy.events.Process(self.env, self.send_data_to_output([parsed_message], delay))

                # Acknowledge the message
                consumer.acknowledge(msg)
                yield
            except Exception as e:
                print(f"Error processing message: {e}")
                consumer.negative_acknowledge(msg)
    # def if message['type'] != 'subscribe':
    #                 simtime, message_dict = ast.literal_eval( message['data']) #type: float, Dict[str, Any]
    #                 print( self.log_prefix(message_dict['ID']) + "Received message from channel: |{}| for simtime |{}| Now: |{}|".format(message['channel'], simtime, self.env.now))
    #                 processing_time: float              = max(0.0,simtime - self.env.now)
    #                 delay: float                        = processing_time
    #                 new_data_list: List[Dict[str, Any]] = [ message_dict ]
    #                 simpy.events.Process(self.env,
    #                                         self.send_data_to_output(new_data_list, processing_time))
    def execute(self):
        """Execute function, part of simpy functionality"""
        yield 0.0, 0.0, []

        while True:
            msg = self.consumer.receive()
            self.consumer.acknowledge(msg)

            message = msg.data().decode('utf-8')

            try:
                parsed_message = json.loads(message)
                id: str = str(uuid.uuid4())
                parsed_message['ID'] = id
                parsed_message[self.msg_size_key] = 10
                parsed_message['simtime_arrived'] = self.env.now
                print(self.log_prefix(parsed_message['ID']) + f"Received message: {message}")
                #import pudb; pu.db
                simtime_of_msg = parsed_message.get(self.simtime_field_name, self.env.now)
                time_to_send_data_out = simtime_of_msg - self.env.now
                # delay_till_get_next_msg,
                # time_to_send_data_out,
                yield self.poll_frequency_secs, time_to_send_data_out, [parsed_message]
            except json.JSONDecodeError as e:
                print(self.log_prefix() + f"Error parsing JSON message: {e}")
                print(self.log_prefix() + f"Raw message content: {message}")
                yield self.poll_frequency_secs, 0.0, []
