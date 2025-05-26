""" Parse JSON Message node converts JSON strings to Pydantic model instances.

This node takes a JSON string stored in a message key and converts it into a 
Pydantic class instance based on the pydantic_type configuration parameter.

"""
from simpy.core import Environment
from typing import List, Dict, Tuple, Any, Optional, Callable
import json
import logging

from nodes.core.base import BaseNode
from pydantic_models.simulator_interfaces import TaskAssignment, SimulatorControlMessage, CollectedTargetData


class ParseJsonMessage(BaseNode):
    """ParseJsonMessage class"""

    def __init__(self, env: Environment, name: str, configuration: Dict[str, Any]):
        """Initialize ParseJsonMessage class"""
        super().__init__(env, name, configuration, self.execute())
        
        # Initialize logger
        self.logger = logging.getLogger(f"{self.__class__.__name__}_{name}")
        
        # Node Reserve Time
        self._processing_delay: Callable[[], Optional[float]] = self.setFloatFromConfig(
            "time_processing", 0.0
        )
        # Message Delay Time
        self._time_delay: Callable[[], Optional[float]] = self.setFloatFromConfig(
            "time_delay", 0.0
        )
        
        # Configuration parameters
        self._json_key = self.setStringFromConfig("json_key", "json_data")
        self._pydantic_type = self.setStringFromConfig("pydantic_types", "TaskAssignment")
        self._result_key = self.setStringFromConfig("result_key", "parsed_object")
        self._error_key = self.setStringFromConfig("error_key", "parse_error")
        self._preserve_json = self.setBoolFromConfig("preserve_json", True)
        self._successful_type_key = self.setStringFromConfig("successful_type_key", "successful_type")
        self._write_out_field_list = configuration.get("write_out_field_list", [])
        
        # Parse pydantic_types as list if it's a string
        pydantic_type_config = configuration.get("pydantic_types", "TaskAssignment")
        if isinstance(pydantic_type_config, str):
            self._pydantic_types = [pydantic_type_config]
        elif isinstance(pydantic_type_config, list):
            self._pydantic_types = pydantic_type_config
        else:
            self._pydantic_types = ["TaskAssignment"]
        
        # Map of available Pydantic classes
        self.pydantic_classes = {
            "TaskAssignment": TaskAssignment,
            "SimulatorControlMessage": SimulatorControlMessage,
            "CollectedTargetData": CollectedTargetData
        }
        
        self.env.process(self.run())

    @property
    def time_delay(self) -> Optional[float]:
        return self._time_delay()

    @property
    def json_key(self) -> Optional[str]:
        return self._json_key()

    @property
    def pydantic_type(self) -> Optional[str]:
        return self._pydantic_type()
    
    @property
    def pydantic_types(self) -> List[str]:
        return self._pydantic_types

    @property
    def result_key(self) -> Optional[str]:
        return self._result_key()

    @property
    def error_key(self) -> Optional[str]:
        return self._error_key()

    @property
    def preserve_json(self) -> bool:
        return self._preserve_json()

    @property
    def successful_type_key(self) -> Optional[str]:
        return self._successful_type_key()

    @property
    def write_out_field_list(self):
        return self._write_out_field_list

    def parse_json_to_pydantic(self, json_data: str, pydantic_types: List[str]) -> Tuple[Any, Optional[str], Optional[str]]:
        """
        Parse JSON string to Pydantic model instance, trying multiple types.
        
        Args:
            json_data: JSON string to parse
            pydantic_types: List of Pydantic class names to try
            
        Returns:
            Tuple of (parsed_object, successful_type, error_message)
        """
        # Parse JSON string to dictionary first
        try:
            if isinstance(json_data, str):
                data_dict = json.loads(json_data)
            elif isinstance(json_data, dict):
                data_dict = json_data
            else:
                return None, None, f"Invalid JSON data type: {type(json_data)}. Expected str or dict."
        except json.JSONDecodeError as e:
            return None, None, f"JSON decode error: {str(e)}"
        
        # Try each pydantic type in order
        errors = []
        for pydantic_type in pydantic_types:
            try:
                # Check if the type is available
                if pydantic_type not in self.pydantic_classes:
                    error_msg = f"Unknown pydantic type: {pydantic_type}. Available types: {list(self.pydantic_classes.keys())}"
                    errors.append(f"{pydantic_type}: {error_msg}")
                    continue
                
                pydantic_class = self.pydantic_classes[pydantic_type]
                
                # Try to create Pydantic model instance
                parsed_object = pydantic_class(**data_dict)
                
                # Success! Return the parsed object and the successful type
                return parsed_object, pydantic_type, None
                
            except Exception as e:
                errors.append(f"{pydantic_type}: {str(e)}")
                continue
        
        # If we get here, none of the types worked
        combined_errors = "; ".join(errors)
        return None, None, f"Failed to parse JSON with any of the specified types: {combined_errors}"

    def execute(self):
        """Simpy execution code"""
        delay: float = 0.0
        processing_time: float = delay
        data_out_list: List[Tuple] = []
        
        while True:
            data_in = yield (delay, processing_time, data_out_list)

            if data_in:
                msg = data_in.copy()
                delay = self.time_delay
                
                # Get configuration values from input or defaults
                json_key = msg.get('json_key', self.json_key)
                pydantic_types_input = msg.get('pydantic_types', self.pydantic_types)
                result_key = msg.get('result_key', self.result_key)
                error_key = msg.get('error_key', self.error_key)
                preserve_json = msg.get('preserve_json', self.preserve_json)
                successful_type_key = msg.get('successful_type_key', self.successful_type_key)
                
                # Ensure pydantic_types is a list
                if isinstance(pydantic_types_input, str):
                    pydantic_types = [pydantic_types_input]
                elif isinstance(pydantic_types_input, list):
                    pydantic_types = pydantic_types_input
                else:
                    pydantic_types = self.pydantic_types
                
                # Check if the JSON key exists in the message
                if json_key not in msg:
                    # JSON key not found, pass through unchanged
                    print(
                        self.log_prefix(msg.get("ID", "unknown"))
                        + f"JSON key '{json_key}' not found in message, passing through unchanged"
                    )
                else:
                    # Parse the JSON data
                    json_data = msg[json_key]
                    parsed_object, successful_type, error_msg = self.parse_json_to_pydantic(json_data, pydantic_types)
                    
                    if error_msg:
                        # Parsing failed with all types, pass through unchanged
                        self.logger.warning(f"Failed to parse JSON with any pydantic type: {error_msg}")
                        print(
                            self.log_prefix(msg.get("ID", "unknown"))
                            + f"Failed to parse JSON with types {pydantic_types}, passing through unchanged: {error_msg}"
                        )
                    else:
                        # Parsing successful
                        msg[result_key] = parsed_object
                        msg[successful_type_key] = successful_type
                        
                        # Copy specified fields to output message
                        write_out_fields = msg.get('write_out_field_list', self.write_out_field_list)
                        if write_out_fields:
                            if write_out_fields == "All Fields" or (isinstance(write_out_fields, list) and "All Fields" in write_out_fields):
                                # Copy all pydantic fields
                                for field_name, field_value in parsed_object.__dict__.items():
                                    msg[field_name] = field_value
                            elif isinstance(write_out_fields, list):
                                # Copy only specified fields
                                for field_name in write_out_fields:
                                    if hasattr(parsed_object, field_name):
                                        msg[field_name] = getattr(parsed_object, field_name)
                        
                        # Remove the original JSON if not preserving
                        if not preserve_json:
                            del msg[json_key]
                        
                        # Clear any previous error
                        if error_key in msg:
                            del msg[error_key]
                        
                        print(
                            self.log_prefix(msg.get("ID", "unknown"))
                            + f"Successfully parsed JSON to {successful_type} object in key '{result_key}'"
                        )

                processing_time = self._processing_delay()
                data_out_list = [msg]
            else:
                data_out_list = []

    # def run(self):
    #     """
    #     Run the node in the simulation environment.
    #     """
    #     while True:
    #         # Wait for input data
    #         data_in = yield self.env.in_queue.get()
            
    #         # Get node execution details
    #         delay, processing_time, data_out_list = self.send(data_in)
            
    #         # Simulate processing time
    #         yield self.env.timeout(processing_time)
            
    #         # Handle delay
    #         if delay > 0:
    #             yield self.env.timeout(delay)
                
    #         # Send output data
    #         for data_out in data_out_list:
    #             self.env.out_queue.put(data_out)