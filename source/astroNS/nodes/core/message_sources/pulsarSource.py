

import pandas as pd
import pulsar
import json
import uuid
import simpy
from datetime import datetime

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
        self.poll_frequency_secs: float = configuration.get("poll_frequency_secs", 10.0)
        self.timeout_ms: int = int(configuration.get("timeout_secs", 5.0) * 1000)  # Convert to milliseconds
        self.retry_on_connection_error: bool = configuration.get("retry_on_connection_error", True)
        self.max_retry_attempts: int = configuration.get("max_retry_attempts", 3)
        self.retry_delay_secs: float = configuration.get("retry_delay_secs", 10.0)
        self.generates_data_only: bool = True

        # Initialize retry tracking
        self.current_retry_count: int = 0
        self.last_retry_time: float = 0.0

        # Initialize connection with retry logic
        self.client = None
        self.consumer = None
        self.sub_successfull = self._initialize_subscription()



        self.env.process(self.run())

    def _initialize_subscription(self):
        """Initialize Pulsar subscription with retry logic"""
        for attempt in range(self.max_retry_attempts):
            try:
                print(self.log_prefix() + f"Attempting Pulsar connection (attempt {attempt + 1}/{self.max_retry_attempts})")

                if self.client is None:
                    self.client = pulsar.Client(self.pulsar_server)

                self.consumer = self.client.subscribe(self.topic_name,
                                                      subscription_name=self.subscription_name)

                print(self.log_prefix() + f"Successfully connected to Pulsar topic: {self.topic_name}")
                self.current_retry_count = 0  # Reset retry count on success
                return True

            except Exception as e:
                print(self.log_prefix() + f"Connection attempt {attempt + 1} failed: {e}")

                # Clean up failed connection
                self._cleanup_connection()

                if attempt < self.max_retry_attempts - 1:
                    print(self.log_prefix() + f"Retrying in {self.retry_delay_secs} seconds...")
                    import time
                    time.sleep(self.retry_delay_secs)
                else:
                    print(self.log_prefix() + f"All {self.max_retry_attempts} connection attempts failed")

        return False

    def _cleanup_connection(self):
        """Clean up Pulsar client and consumer connections"""
        try:
            if hasattr(self, 'consumer') and self.consumer:
                self.consumer.close()
                self.consumer = None
        except Exception as e:
            print(self.log_prefix() + f"Error closing consumer: {e}")

        try:
            if hasattr(self, 'client') and self.client:
                self.client.close()
                self.client = None
        except Exception as e:
            print(self.log_prefix() + f"Error closing client: {e}")

    def _should_retry_connection(self):
        """Determine if we should retry connection based on configuration and timing"""
        if not self.retry_on_connection_error:
            return False

        if self.current_retry_count >= self.max_retry_attempts:
            # Check if enough time has passed to reset retry counter
            current_time = self.env.now
            if current_time - self.last_retry_time >= self.retry_delay_secs * self.max_retry_attempts:
                self.current_retry_count = 0
                return True
            return False

        return True

    def cleanup(self):
        """Clean up Pulsar client and consumer connections"""
        self._cleanup_connection()

    def __del__(self):
        """Destructor to ensure cleanup on object deletion"""
        self.cleanup()

    def message_listener(self, consumer, msg):
            """Callback function for handling incoming messages asynchronously"""
            #import pudb; pu.db
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
        if not self.sub_successfull:
            print(self.log_prefix() + "Subscription failed. Ending Simulation")
            exit()
        while True:
            # Check if consumer is available
            # if self.consumer is None:
            #     if self._should_retry_connection():
            #         print(self.log_prefix() + f"Consumer not available, attempting reconnection (retry {self.current_retry_count + 1}/{self.max_retry_attempts})")
            #         self.current_retry_count += 1
            #         self.last_retry_time = self.env.now

            #         try:
            #             if self.client is None:
            #                 self.client = pulsar.Client(self.pulsar_server)
            #             self.consumer = self.client.subscribe(self.topic_name,
            #                                                   subscription_name=self.subscription_name)
            #             print(self.log_prefix() + f"Successfully reconnected to Pulsar topic: {self.topic_name}")
            #             self.current_retry_count = 0  # Reset on success
            #         except Exception as e:
            #             print(self.log_prefix() + f"Reconnection attempt failed: {e}")
            #             self._cleanup_connection()
            #             yield self.poll_frequency_secs, 0.0, []
            #             continue
            #     else:
            #         print(self.log_prefix() + f"Maximum retry attempts reached, waiting before next attempt")
            #         yield self.poll_frequency_secs, 0.0, []
            #         continue

            try:
                # Attempt to receive message with timeout
                print(self.log_prefix() + f"Waiting to receive message with timeout {self.timeout_ms} ms")
                msg = self.consumer.receive(timeout_millis=self.timeout_ms)
                self.consumer.acknowledge(msg)

                message = msg.data().decode('utf-8')

                try:
                    message_data = json.loads(message)
                    new_message = message_data
                    new_message['json_data'] = message_data
                    id: str = str(uuid.uuid4())
                    new_message['ID'] = id
                    new_message[self.msg_size_key] = 10
                    new_message['simtime_arrived'] = self.env.now
                    print(self.log_prefix(new_message['ID']) + f"Received message: {message}")
                    #import pudb; pu.db
                    simtime_of_msg = new_message.get(self.simtime_field_name, self.env.now)
                    print(self.log_prefix(new_message['ID']) + f"Simtime of message: {simtime_of_msg}")
                    time_to_send_data_out = simtime_of_msg - self.env.now
                    # delay_till_get_next_msg,
                    # time_to_send_data_out,
                    # Hack for now
                    if ('message_type' in new_message) and (new_message['message_type'] == 'time_advance'):
                        advance_time_str = new_message['payload']['TimeStepEndTime']
                        advance_time = datetime.fromisoformat(advance_time_str)
                        check_topic_at_simtime  = (advance_time - self.env.now_datetime()).total_seconds()
                        yield check_topic_at_simtime, time_to_send_data_out,[new_message]
                    else:
                        yield self.poll_frequency_secs, time_to_send_data_out, [new_message]
                except json.JSONDecodeError as e:
                    print(self.log_prefix() + f"Error parsing JSON message: {e}")
                    print(self.log_prefix() + f"Raw message content: {message}")
                    yield self.poll_frequency_secs, 0.0, []

            except Exception as e:
                # Handle timeout or other receive errors
                if "timeout" in str(e).lower():
                    print(self.log_prefix() + f"No message received within {self.timeout_ms}ms timeout, polling again")

                elif "connection" in str(e).lower() or "subscribe" in str(e).lower():
                    print(self.log_prefix() + f"Connection/subscription error: {e}")
                    # Reset consumer to trigger reconnection logic
                    self._cleanup_connection()

                    if self.retry_on_connection_error:
                        print(self.log_prefix() + f"Will attempt reconnection on next cycle")
                    else:
                        print(self.log_prefix() + f"Retry on connection error disabled")
                else:
                    print(self.log_prefix() + f"Error receiving message: {e}")
                # Yield for poll frequency duration when error occurs
                yield self.poll_frequency_secs, 0.0, []
