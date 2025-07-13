""" Process Sim Time Advance Command Payload node advances simulation time.

This node takes a SimTimeAdvanceCommandPayload and calculates the delay in seconds
based on the TimeStepEndTime relative to the simulation's epoch. It creates a message
with the calculated delay to advance the simulation time.

"""
from simpy.core import Environment
from typing import List, Dict, Tuple, Any, Optional, Callable
from datetime import datetime
import logging

from nodes.core.base import BaseNode
from nodes.pydantic_models.two_six_messages import (
    SimTimeAdvanceCommandPayload,
    SimulationStepCompletePayload,
    SimulationStatus,
    WrappedOutputMessage,
    OutputMessageType
)


class ProcessSimTimeAdvanceCommandPayload(BaseNode):
    """ProcessSimTimeAdvanceCommandPayload class"""

    def __init__(self, env: Environment, name: str, configuration: Dict[str, Any]):
        """Initialize ProcessSimTimeAdvanceCommandPayload class"""
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
        self._payload_key = self.setStringFromConfig("payload_key", "unwrapped_payload")
        self._delay_key = self.setStringFromConfig("delay_key", "delay_seconds")
        self._error_key = self.setStringFromConfig("error_key", "time_advance_error")
        self._sim_time_key = self.setStringFromConfig("sim_time_key", "sim_time_seconds")
        self._time_step_start_key = self.setStringFromConfig("time_step_start_key", "time_step_start_time")
        self._time_step_end_key = self.setStringFromConfig("time_step_end_key", "time_step_end_time")
        self._wrapped_output_key = self.setStringFromConfig("wrapped_output_key", "wrapped_output_message")

        self.env.process(self.run())

    @property
    def time_delay(self) -> Optional[float]:
        return self._time_delay()

    @property
    def payload_key(self) -> Optional[str]:
        return self._payload_key()

    @property
    def delay_key(self) -> Optional[str]:
        return self._delay_key()

    @property
    def error_key(self) -> Optional[str]:
        return self._error_key()

    @property
    def sim_time_key(self) -> Optional[str]:
        return self._sim_time_key()

    @property
    def time_step_start_key(self) -> Optional[str]:
        return self._time_step_start_key()

    @property
    def time_step_end_key(self) -> Optional[str]:
        return self._time_step_end_key()

    @property
    def wrapped_output_key(self) -> Optional[str]:
        return self._wrapped_output_key()

    def calculate_sim_time_delay(self, payload: SimTimeAdvanceCommandPayload) -> Tuple[Optional[float], Optional[float], Optional[str]]:
        """
        Calculate simulation time delay based on TimeStepEndTime.

        Args:
            payload: SimTimeAdvanceCommandPayload instance

        Returns:
            Tuple of (delay_seconds, sim_time_seconds, error_message)
        """
        try:
            # Get the TimeStepEndTime from the payload
            # import pudb;pu.db
            time_step_end_time = payload.time_step_end_time

            #advance_time = datetime.fromisoformat(advance_time_str)
            #check_topic_at_simtime  = (advance_time - self.env.now_datetime()).total_seconds()

            # Check if env has epoch attribute
            if not hasattr(self.env, 'epoch'):
                return None, None, "Simulation environment does not have an epoch attribute"

            # Calculate the delta between TimeStepEndTime and simulation epoch
            time_delta = time_step_end_time - self.env.now_datetime()

            # Convert to seconds
            delay_seconds = time_delta.total_seconds()

            # Check if the time is negative
            if delay_seconds < 0:
                error_msg = f"Negative time advance calculated: {delay_seconds} seconds. TimeStepEndTime ({time_step_end_time}) is before simulation epoch ({self.env.epoch})"
                return None, None, error_msg

            # Calculate sim time seconds (same as delay in this case)
            sim_time_seconds = delay_seconds

            return delay_seconds, sim_time_seconds, None

        except Exception as e:
            return None, None, f"Error calculating simulation time delay: {str(e)}"

    def process_payload(self, payload: Any) -> Tuple[Optional[float], Optional[float], Optional[str]]:
        """
        Process the payload to extract time advance information.

        Args:
            payload: Expected to be SimTimeAdvanceCommandPayload instance

        Returns:
            Tuple of (delay_seconds, sim_time_seconds, error_message)
        """
        # Check if payload is the correct type
        if not isinstance(payload, SimTimeAdvanceCommandPayload):
            return None, None, f"Invalid payload type: {type(payload)}. Expected SimTimeAdvanceCommandPayload."

        return self.calculate_sim_time_delay(payload)

    def create_simulation_step_complete_payload(self, time_step_end_time: datetime) -> SimulationStepCompletePayload:
        """
        Create a SimulationStepCompletePayload for the time advance completion.

        Args:
            time_step_end_time: The TimeStepEndTime from the advance command

        Returns:
            SimulationStepCompletePayload instance
        """
        return SimulationStepCompletePayload(
            TimeStepEndTime=time_step_end_time,
            Status=SimulationStatus.COMPLETED,
            Message=f"Time advanced to {time_step_end_time.isoformat()}"
        )

    def create_wrapped_output_message(self, sim_step_complete_payload: SimulationStepCompletePayload) -> WrappedOutputMessage:
        """
        Create a WrappedOutputMessage containing the SimulationStepCompletePayload.

        Args:
            sim_step_complete_payload: SimulationStepCompletePayload instance

        Returns:
            WrappedOutputMessage instance
        """
        return WrappedOutputMessage(
            message_type=OutputMessageType.SIMULATION_STEP_COMPLETE,
            payload=sim_step_complete_payload
        )

    def execute(self):
        """Simpy execution code"""
        delay: float = 0.0
        processing_time: float = delay
        data_out_list: List[Tuple] = []

        while True:
            data_in = yield (processing_time, delay - 1, data_out_list)

            if data_in:
                msg = data_in.copy()
                delay = self.time_delay

                # Get configuration values from input or defaults
                payload_key = msg.get('payload_key', self.payload_key)
                delay_key = msg.get('delay_key', self.delay_key)
                error_key = msg.get('error_key', self.error_key)
                sim_time_key = msg.get('sim_time_key', self.sim_time_key)
                time_step_start_key = msg.get('time_step_start_key', self.time_step_start_key)
                time_step_end_key = msg.get('time_step_end_key', self.time_step_end_key)
                wrapped_output_key = msg.get('wrapped_output_key', self.wrapped_output_key)

                # Check if the payload key exists in the message
                if payload_key not in msg:
                    # Payload key not found, pass through unchanged
                    print(
                        self.log_prefix(msg.get("ID", "unknown"))
                        + f"Payload key '{payload_key}' not found in message, passing through unchanged"
                    )
                else:
                    # Process the payload
                    payload = msg[payload_key]
                    delay_seconds, sim_time_seconds, error_msg = self.process_payload(payload)

                    if error_msg:
                        # Processing failed, store error and pass through
                        msg[error_key] = error_msg
                        self.logger.error(f"Failed to process time advance command: {error_msg}")
                        print(
                            self.log_prefix(msg.get("ID", "unknown"))
                            + f"ERROR: {error_msg}"
                        )
                    else:
                        # Processing successful
                        msg[delay_key] = delay_seconds
                        delay = sim_time_seconds
                        msg[sim_time_key] = sim_time_seconds

                        # Also store the individual time fields for easy access
                        if isinstance(payload, SimTimeAdvanceCommandPayload):
                            msg[time_step_start_key] = payload.time_step_start_time
                            msg[time_step_end_key] = payload.time_step_end_time

                            # Create SimulationStepCompletePayload
                            sim_step_complete_payload = self.create_simulation_step_complete_payload(
                                payload.time_step_end_time
                            )

                            # Create WrappedOutputMessage
                            wrapped_output_message = self.create_wrapped_output_message(sim_step_complete_payload)

                            # Store the wrapped message in the configured key
                            msg[wrapped_output_key] = wrapped_output_message

                        # Clear any previous error
                        if error_key in msg:
                            del msg[error_key]

                        print(
                            self.log_prefix(msg.get("ID", "unknown"))
                            + f"Successfully calculated time advance: {delay_seconds} seconds to reach {payload.time_step_end_time}"
                        )
                        print(
                            self.log_prefix(msg.get("ID", "unknown"))
                            + f"Created WrappedOutputMessage with SimulationStepCompletePayload stored in '{wrapped_output_key}'"
                        )

                processing_time = self._processing_delay()
                data_out_list = [msg]
            else:
                data_out_list = []
