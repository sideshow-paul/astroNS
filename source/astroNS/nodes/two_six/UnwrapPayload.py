""" Unwrap Payload node extracts payloads from wrapped message objects.

This node takes a wrapped message (WrappedInputMessage or WrappedOutputMessage)
and extracts the payload, storing it in a specified message key. The payload
can be SimTimeAdvanceCommandPayload, SimTaskBatchPayload, SimulationStepCompletePayload,
or CollectedTargetDataPayload.

"""
from simpy.core import Environment
from typing import List, Dict, Tuple, Any, Optional, Callable
import logging

from nodes.core.base import BaseNode
from nodes.pydantic_models.two_six_messages import (
    WrappedInputMessage,
    WrappedOutputMessage,
    SimTimeAdvanceCommandPayload,
    SimTaskBatchPayload,
    SimulationResetPayload,
    SimulationStepCompletePayload,
    CollectedTargetDataPayload,
    InputMessageType,
    OutputMessageType
)


class UnwrapPayload(BaseNode):
    """UnwrapPayload class"""

    def __init__(self, env: Environment, name: str, configuration: Dict[str, Any]):
        """Initialize UnwrapPayload class"""
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
        self._wrapped_message_key = self.setStringFromConfig("wrapped_message_key", "wrapped_message")
        self._store_unwrapped_payload_key = self.setStringFromConfig("store_unwrapped_payload_key", "unwrapped_payload")
        self._error_key = self.setStringFromConfig("error_key", "unwrap_error")
        self._message_type_key = self.setStringFromConfig("message_type_key", "message_type")
        self._payload_type_key = self.setStringFromConfig("payload_type_key", "payload_type")
        self._write_out_field_list = configuration.get("write_out_field_list", [])

        self.env.process(self.run())

    @property
    def time_delay(self) -> Optional[float]:
        return self._time_delay()

    @property
    def wrapped_message_key(self) -> Optional[str]:
        return self._wrapped_message_key()

    @property
    def store_unwrapped_payload_key(self) -> Optional[str]:
        return self._store_unwrapped_payload_key()

    @property
    def error_key(self) -> Optional[str]:
        return self._error_key()

    @property
    def message_type_key(self) -> Optional[str]:
        return self._message_type_key()

    @property
    def payload_type_key(self) -> Optional[str]:
        return self._payload_type_key()

    @property
    def write_out_field_list(self):
        return self._write_out_field_list

    def unwrap_payload(self, wrapped_message: Any) -> Tuple[Any, Optional[str], Optional[str], Optional[str]]:
        """
        Extract payload from wrapped message.

        Args:
            wrapped_message: WrappedInputMessage or WrappedOutputMessage instance

        Returns:
            Tuple of (payload, message_type, payload_type, error_message)
        """
        try:
            # Check if it's a WrappedInputMessage
            if isinstance(wrapped_message, WrappedInputMessage):
                payload = wrapped_message.payload
                message_type = wrapped_message.message_type

                # Determine payload type based on message type
                if message_type == InputMessageType.TIME_ADVANCE:
                    payload_type = "SimTimeAdvanceCommandPayload"
                elif message_type == InputMessageType.TASK_BATCH:
                    payload_type = "SimTaskBatchPayload"
                elif message_type == InputMessageType.SIMULATION_RESET:
                    payload_type = "SimulationResetPayload"
                else:
                    return None, None, None, f"Unknown input message type: {message_type}"

                return payload, message_type, payload_type, None

            # Check if it's a WrappedOutputMessage
            elif isinstance(wrapped_message, WrappedOutputMessage):
                payload = wrapped_message.payload
                message_type = wrapped_message.message_type

                # Determine payload type based on message type
                if message_type == OutputMessageType.SIMULATION_STEP_COMPLETE:
                    payload_type = "SimulationStepCompletePayload"
                elif message_type == OutputMessageType.COLLECTED_TARGET_DATA:
                    payload_type = "CollectedTargetDataPayload"
                else:
                    return None, None, None, f"Unknown output message type: {message_type}"

                return payload, message_type, payload_type, None

            else:
                return None, None, None, f"Invalid wrapped message type: {type(wrapped_message)}. Expected WrappedInputMessage or WrappedOutputMessage."

        except Exception as e:
            return None, None, None, f"Error unwrapping payload: {str(e)}"

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
                wrapped_message_key = msg.get('wrapped_message_key', self.wrapped_message_key)
                store_unwrapped_payload_key = msg.get('store_unwrapped_payload_key', self.store_unwrapped_payload_key)
                error_key = msg.get('error_key', self.error_key)
                message_type_key = msg.get('message_type_key', self.message_type_key)
                payload_type_key = msg.get('payload_type_key', self.payload_type_key)

                # Check if the wrapped message key exists in the message
                if wrapped_message_key not in msg:
                    # Wrapped message key not found, pass through unchanged
                    print(
                        self.log_prefix(msg.get("ID", "unknown"))
                        + f"Wrapped message key '{wrapped_message_key}' not found in message, passing through unchanged"
                    )
                else:
                    # Unwrap the payload
                    wrapped_message = msg[wrapped_message_key]
                    payload, message_type, payload_type, error_msg = self.unwrap_payload(wrapped_message)

                    if error_msg:
                        # Unwrapping failed, store error and pass through
                        msg[error_key] = error_msg
                        self.logger.warning(f"Failed to unwrap payload: {error_msg}")
                        print(
                            self.log_prefix(msg.get("ID", "unknown"))
                            + f"Failed to unwrap payload, passing through unchanged: {error_msg}"
                        )
                    else:
                        # Unwrapping successful
                        msg[store_unwrapped_payload_key] = payload
                        msg[message_type_key] = message_type
                        msg[payload_type_key] = payload_type

                        # Copy specified fields to output message
                        write_out_fields = msg.get('write_out_field_list', self.write_out_field_list)
                        if write_out_fields:
                            if write_out_fields == "All" or (isinstance(write_out_fields, list) and "All" in write_out_fields):
                                # Copy all payload fields
                                for field_name, field_value in payload.__dict__.items():
                                    msg[field_name] = field_value
                            elif isinstance(write_out_fields, list):
                                # Copy only specified fields
                                for field_name in write_out_fields:
                                    if hasattr(payload, field_name):
                                        msg[field_name] = getattr(payload, field_name)

                        # Clear any previous error
                        if error_key in msg:
                            del msg[error_key]

                        print(
                            self.log_prefix(msg.get("ID", "unknown"))
                            + f"Successfully unwrapped {payload_type} payload from {message_type} message"
                        )

                processing_time = self._processing_delay()
                data_out_list = [msg]
            else:
                data_out_list = []
