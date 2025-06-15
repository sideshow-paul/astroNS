""" Wrap Payload node creates WrappedOutputMessage from payload data.

This node creates a payload (CollectedTargetDataPayload or SimulationStepCompletePayload)
from message data and wraps it in a WrappedOutputMessage for output to external systems.

"""
from simpy.core import Environment
from typing import List, Dict, Tuple, Any, Optional, Callable
from datetime import datetime
import logging
import uuid

from nodes.core.base import BaseNode
from nodes.pydantic_models.two_six_messages import (
    WrappedOutputMessage,
    CollectedTargetDataPayload,
    SimulationStepCompletePayload,
    SimulationStatus,
    OutputMessageType
)


class WrapPayload(BaseNode):
    """WrapPayload class"""

    def __init__(self, env: Environment, name: str, configuration: Dict[str, Any]):
        """Initialize WrapPayload class"""
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
        self._wrap_payload_type = self.setStringFromConfig("wrap_payload_type", "CollectedTargetDataPayload")
        self._wrapped_message_key = self.setStringFromConfig("wrapped_message_key", "wrapped_output_message")
        self._error_key = self.setStringFromConfig("error_key", "wrap_error")
        self._source_data_keys = configuration.get("source_data_keys", [])
        self._required_fields = configuration.get("required_fields", {})
        self._default_values = configuration.get("default_values", {})

        self.env.process(self.run())

    @property
    def time_delay(self) -> Optional[float]:
        return self._time_delay()

    @property
    def wrap_payload_type(self) -> Optional[str]:
        return self._wrap_payload_type()

    @property
    def wrapped_message_key(self) -> Optional[str]:
        return self._wrapped_message_key()

    @property
    def error_key(self) -> Optional[str]:
        return self._error_key()

    @property
    def source_data_keys(self) -> List[str]:
        return self._source_data_keys

    @property
    def required_fields(self) -> Dict[str, str]:
        return self._required_fields

    @property
    def default_values(self) -> Dict[str, Any]:
        return self._default_values

    def create_collected_target_data_payload(self, msg: Dict[str, Any]) -> Tuple[Optional[CollectedTargetDataPayload], Optional[str]]:
        """
        Create a CollectedTargetDataPayload from message data.

        Args:
            msg: Message containing the data

        Returns:
            Tuple of (payload, error_message)
        """
        try:
            # Extract required fields with fallbacks
            payload_data = {
                'collected_target_data_id': msg.get('collected_target_data_id', str(uuid.uuid4())),
                'assignment_id': msg.get('assignment_id', msg.get('task_id', 'unknown')),
                'opportunity_id': int(msg.get('opportunity_id', 0)),
                'task_id': int(msg.get('original_task_id', msg.get('task_id', 0))),
                'target_id': int(msg.get('target_id', 0)),
                'satellite_name': msg.get('satellite_name', msg.get('satellite_id', 'unknown')),
                'agent_id': msg.get('agent_id', 'unknown'),
                'actual_collection_start_time': self._get_datetime_field(msg, 'start_time', 'actual_collection_start_time'),
                'actual_collection_end_time': self._get_datetime_field(msg, 'end_time', 'actual_collection_end_time'),
                'aimpoint_latitude': float(msg.get('aimpoint_latitude', 0.0)),
                'aimpoint_longitude': float(msg.get('aimpoint_longitude', 0.0)),
                'simulated_success_status': msg.get('simulated_success_status', True),
                'failure_reason': msg.get('failure_reason'),
                'simulated_quality_score': msg.get('simulated_quality_score'),
                'simulated_gsd_cm': self._convert_gsd_to_cm(msg.get('gsd_m_per_px')),
                'simulated_cloud_cover_percent': msg.get('simulated_cloud_cover_percent'),
                'simulated_area_covered_sqkm': msg.get('simulated_area_covered_sqkm'),
                'collected_metrics': msg.get('collected_metrics'),
                'additional_sim_metadata': msg.get('additional_sim_metadata'),
                'notes_from_simulator': msg.get('notes_from_simulator')
            }

            # Apply any configured default values
            for key, value in self.default_values.items():
                if key not in payload_data or payload_data[key] is None:
                    payload_data[key] = value

            # Apply field mappings from configuration
            for field_name, source_key in self.required_fields.items():
                if source_key in msg:
                    payload_data[field_name] = msg[source_key]

            # Create the payload
            payload = CollectedTargetDataPayload(**payload_data)
            return payload, None

        except Exception as e:
            return None, f"Error creating CollectedTargetDataPayload: {str(e)}"

    def create_simulation_step_complete_payload(self, msg: Dict[str, Any]) -> Tuple[Optional[SimulationStepCompletePayload], Optional[str]]:
        """
        Create a SimulationStepCompletePayload from message data.

        Args:
            msg: Message containing the data

        Returns:
            Tuple of (payload, error_message)
        """
        try:
            # Extract required fields with fallbacks
            time_step_end_time = self._get_datetime_field(msg, 'TimeStepEndTime', 'time_step_end_time')
            if time_step_end_time is None:
                time_step_end_time = self.env.now_datetime()

            status_value = msg.get('Status', msg.get('status', 'Completed'))
            if isinstance(status_value, str):
                try:
                    status = SimulationStatus(status_value)
                except ValueError:
                    status = SimulationStatus.COMPLETED
            else:
                status = SimulationStatus.COMPLETED

            message_text = msg.get('Message', msg.get('message'))

            # Apply any configured default values
            payload_data = {
                'TimeStepEndTime': time_step_end_time,
                'Status': status,
                'Message': message_text
            }

            # Apply field mappings from configuration
            for field_name, source_key in self.required_fields.items():
                if source_key in msg:
                    payload_data[field_name] = msg[source_key]

            # Apply default values
            for key, value in self.default_values.items():
                if key not in payload_data or payload_data[key] is None:
                    payload_data[key] = value

            # Create the payload
            payload = SimulationStepCompletePayload(**payload_data)
            return payload, None

        except Exception as e:
            return None, f"Error creating SimulationStepCompletePayload: {str(e)}"

    def create_wrapped_output_message(self, payload: Any, payload_type: str) -> Tuple[Optional[WrappedOutputMessage], Optional[str]]:
        """
        Create a WrappedOutputMessage containing the payload.

        Args:
            payload: The payload object
            payload_type: Type of the payload

        Returns:
            Tuple of (wrapped_message, error_message)
        """
        try:
            # Determine message type based on payload type
            if payload_type == "CollectedTargetDataPayload":
                message_type = OutputMessageType.COLLECTED_TARGET_DATA
            elif payload_type == "SimulationStepCompletePayload":
                message_type = OutputMessageType.SIMULATION_STEP_COMPLETE
            else:
                return None, f"Unknown payload type: {payload_type}"

            # Create the wrapped message
            wrapped_message = WrappedOutputMessage(
                message_type=message_type,
                payload=payload
            )

            return wrapped_message, None

        except Exception as e:
            return None, f"Error creating WrappedOutputMessage: {str(e)}"

    def _get_datetime_field(self, msg: Dict[str, Any], *field_names: str) -> Optional[datetime]:
        """
        Get a datetime field from the message, trying multiple field names.

        Args:
            msg: Message dictionary
            *field_names: Field names to try

        Returns:
            datetime object or None
        """
        for field_name in field_names:
            if field_name in msg:
                value = msg[field_name]
                if isinstance(value, datetime):
                    return value
                elif isinstance(value, str):
                    try:
                        return datetime.fromisoformat(value.replace('Z', '+00:00'))
                    except (ValueError, AttributeError):
                        continue
                elif isinstance(value, (int, float)):
                    try:
                        return datetime.fromtimestamp(value)
                    except (ValueError, OSError):
                        continue

        return None

    def _convert_gsd_to_cm(self, gsd_m_per_px: Optional[float]) -> Optional[float]:
        """
        Convert GSD from meters per pixel to centimeters per pixel.

        Args:
            gsd_m_per_px: GSD in meters per pixel

        Returns:
            GSD in centimeters per pixel or None
        """
        if gsd_m_per_px is not None:
            return gsd_m_per_px * 100.0
        return None

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
                payload_type = msg.get('wrap_payload_type', self.wrap_payload_type)
                wrapped_message_key = msg.get('wrapped_message_key', self.wrapped_message_key)
                error_key = msg.get('error_key', self.error_key)

                # Create the appropriate payload based on type
                if payload_type == "CollectedTargetDataPayload":
                    payload, payload_error = self.create_collected_target_data_payload(msg)
                elif payload_type == "SimulationStepCompletePayload":
                    payload, payload_error = self.create_simulation_step_complete_payload(msg)
                else:
                    payload = None
                    payload_error = f"Unknown payload type: {payload_type}. Supported types: CollectedTargetDataPayload, SimulationStepCompletePayload"

                if payload_error:
                    # Payload creation failed
                    msg[error_key] = payload_error
                    self.logger.error(f"Failed to create payload: {payload_error}")
                    print(
                        self.log_prefix(msg.get("ID", "unknown"))
                        + f"ERROR: {payload_error}"
                    )
                else:
                    # Create wrapped output message
                    wrapped_message, wrap_error = self.create_wrapped_output_message(payload, payload_type)

                    if wrap_error:
                        # Wrapping failed
                        msg[error_key] = wrap_error
                        self.logger.error(f"Failed to create wrapped message: {wrap_error}")
                        print(
                            self.log_prefix(msg.get("ID", "unknown"))
                            + f"ERROR: {wrap_error}"
                        )
                    else:
                        # Success - store the wrapped message
                        msg[wrapped_message_key] = wrapped_message

                        # Clear any previous error
                        if error_key in msg:
                            del msg[error_key]

                        print(
                            self.log_prefix(msg.get("ID", "unknown"))
                            + f"Successfully created {payload_type} wrapped in WrappedOutputMessage"
                        )

                processing_time = self._processing_delay()
                data_out_list = [msg]
            else:
                data_out_list = []
