import pandas as pd
import pulsar
import json
import uuid

from simpy.core import Environment
from nodes.core.base import BaseNode
from nodes.pydantic_models.simulator_interfaces import TaskAssignment, SimulatorControlMessage, CollectedTargetData

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
        
        # Pydantic model configuration
        self.pydantic_class_name: Optional[str] = configuration.get("pydantic_class", None)
        self.use_pydantic_validation: bool = configuration.get("use_pydantic_validation", False)
        
        # Map of available Pydantic classes
        self.pydantic_classes = {
            "TaskAssignment": TaskAssignment,
            "SimulatorControlMessage": SimulatorControlMessage,
            "CollectedTargetData": CollectedTargetData
        }

        try:
            self.client = pulsar.Client(self.pulsar_server)
            self.producer = self.client.create_producer(self.topic_name)
            print(self.log_prefix() + f"Connected to Pulsar server at {self.pulsar_server}")
        except Exception as e:
            print(self.log_prefix() + f"Failed to connect to Pulsar: {str(e)}")

        self.env.process(self.run())

    def _create_pydantic_object(self, data: Dict[str, Any]):
        """
        Create a Pydantic object from the data dictionary.
        
        Args:
            data: Dictionary containing the data to validate
            
        Returns:
            Pydantic object instance or None if creation fails
        """
        if not self.pydantic_class_name or self.pydantic_class_name not in self.pydantic_classes:
            print(self.log_prefix() + f"Unknown pydantic class: {self.pydantic_class_name}")
            return None
            
        pydantic_class = self.pydantic_classes[self.pydantic_class_name]
        
        try:
            # Create Pydantic object, filtering out fields that don't exist in the model
            model_fields = set(pydantic_class.model_fields.keys())
            filtered_data = {k: v for k, v in data.items() if k in model_fields}
            
            pydantic_obj = pydantic_class(**filtered_data)
            return pydantic_obj
            
        except Exception as e:
            print(self.log_prefix() + f"Failed to create {self.pydantic_class_name} object: {str(e)}")
            return None

    def execute(self):
        """Execute function, part of simpy functionality"""
        delay_till_get_next_msg: float = self.delay
        time_to_send_data_out: float = 0.0
        data_in: Optional[Dict[str, Any]] = None
        data_out_list: List[Dict[str, Any]] = []

        while True:
            data_in = yield #(delay_till_get_next_msg, time_to_send_data_out, data_out_list)

            try:
                # Process the incoming data
                data_out_list = [data_in]

                # Prepare data for sending
                data_in_copy: Dict[str, Any] = data_in.copy()
                data_in_copy['ID'] = str(data_in['ID'])
                data_in_copy['time'] = self.env.now_datetime().isoformat(timespec='microseconds')
                
                # Create Pydantic object if configured
                if self.use_pydantic_validation and self.pydantic_class_name:
                    try:
                        pydantic_obj = self._create_pydantic_object(data_in_copy)
                        if pydantic_obj:
                            # Use the validated Pydantic object's data
                            data_in_copy = pydantic_obj.model_dump()
                            data_in_copy['ID'] = str(data_in['ID'])  # Ensure ID is preserved as string
                            data_in_copy['time'] = self.env.now_datetime().isoformat(timespec='microseconds')
                            print(self.log_prefix(data_in_copy.get("ID", "unknown")) + f"Created {self.pydantic_class_name} object")
                    except Exception as e:
                        print(self.log_prefix(data_in_copy.get("ID", "unknown")) + f"Pydantic validation failed: {str(e)}")
                        # Continue with original data if validation fails

                json_data_in: str = json.dumps(data_in_copy)

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