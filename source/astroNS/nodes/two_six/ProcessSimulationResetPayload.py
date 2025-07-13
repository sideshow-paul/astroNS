""" Process Simulation Reset Payload node handles SimulationResetPayload messages.

This node takes a SimulationResetPayload and processes the simulation reset request,
updating the simulation environment's epoch and state based on the new scenario start time.

"""
from simpy.core import Environment
from typing import List, Dict, Tuple, Any, Optional, Callable
from datetime import datetime
import logging

from nodes.core.base import BaseNode
from nodes.pydantic_models.two_six_messages import (
    SimulationResetPayload
)


class ProcessSimulationResetPayload(BaseNode):
    """ProcessSimulationResetPayload class"""

    def __init__(self, env: Environment, name: str, configuration: Dict[str, Any]):
        """Initialize ProcessSimulationResetPayload class"""
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
        self._error_key = self.setStringFromConfig("error_key", "reset_error")
        self._reset_id_key = self.setStringFromConfig("reset_id_key", "reset_id")
        self._new_scenario_start_key = self.setStringFromConfig("new_scenario_start_key", "new_scenario_start_time")
        self._hard_reset_flag_key = self.setStringFromConfig("hard_reset_flag_key", "hard_reset_database")
        self._reset_complete_key = self.setStringFromConfig("reset_complete_key", "reset_complete")

        self.env.process(self.run())

    @property
    def time_delay(self) -> Optional[float]:
        return self._time_delay()

    @property
    def payload_key(self) -> Optional[str]:
        return self._payload_key()

    @property
    def error_key(self) -> Optional[str]:
        return self._error_key()

    @property
    def reset_id_key(self) -> Optional[str]:
        return self._reset_id_key()

    @property
    def new_scenario_start_key(self) -> Optional[str]:
        return self._new_scenario_start_key()

    @property
    def hard_reset_flag_key(self) -> Optional[str]:
        return self._hard_reset_flag_key()

    @property
    def reset_complete_key(self) -> Optional[str]:
        return self._reset_complete_key()

    def process_reset_payload(self, payload: Any) -> Tuple[Optional[str], Optional[datetime], Optional[bool], Optional[str]]:
        """
        Process the SimulationResetPayload to extract reset information.

        Args:
            payload: Expected to be SimulationResetPayload instance

        Returns:
            Tuple of (reset_id, new_scenario_start_time, hard_reset_database, error_message)
        """
        # Check if payload is the correct type
        if not isinstance(payload, SimulationResetPayload):
            return None, None, None, f"Invalid payload type: {type(payload)}. Expected SimulationResetPayload."

        try:
            reset_id = payload.reset_id
            new_scenario_start_time = payload.new_scenario_start_time
            hard_reset_database = payload.hard_reset_database

            # Validate the new scenario start time
            if not isinstance(new_scenario_start_time, datetime):
                return None, None, None, f"Invalid new_scenario_start_time type: {type(new_scenario_start_time)}. Expected datetime."

            return reset_id, new_scenario_start_time, hard_reset_database, None

        except Exception as e:
            return None, None, None, f"Error processing reset payload: {str(e)}"

    def execute_simulation_reset(self, new_scenario_start_time: datetime, hard_reset: bool) -> bool:
        """
        Execute the simulation reset by updating the environment's epoch.

        Args:
            new_scenario_start_time: New scenario start time
            hard_reset: Whether to perform a hard reset

        Returns:
            bool: True if reset was successful, False otherwise
        """
        try:
            # Update simulation epoch if environment supports it
            if hasattr(self.env, 'epoch'):
                old_epoch = self.env.epoch
                self.env.epoch = new_scenario_start_time
                self.logger.info(f"Simulation epoch updated from {old_epoch} to {new_scenario_start_time}")
            else:
                self.logger.warning("Environment does not have epoch attribute - cannot update simulation time")

            # Additional reset logic could be added here based on hard_reset flag
            if hard_reset:
                self.logger.info("Hard reset requested - additional cleanup may be needed")

            return True

        except Exception as e:
            self.logger.error(f"Failed to execute simulation reset: {str(e)}")
            return False

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
                payload_key = msg.get('payload_key', self.payload_key)
                error_key = msg.get('error_key', self.error_key)
                reset_id_key = msg.get('reset_id_key', self.reset_id_key)
                new_scenario_start_key = msg.get('new_scenario_start_key', self.new_scenario_start_key)
                hard_reset_flag_key = msg.get('hard_reset_flag_key', self.hard_reset_flag_key)
                reset_complete_key = msg.get('reset_complete_key', self.reset_complete_key)

                # Check if the payload key exists in the message
                if payload_key not in msg:
                    # Payload key not found, pass through unchanged
                    print(
                        self.log_prefix(msg.get("ID", "unknown"))
                        + f"Payload key '{payload_key}' not found in message, passing through unchanged"
                    )
                else:
                    # Process the reset payload
                    payload = msg[payload_key]
                    reset_id, new_scenario_start_time, hard_reset_database, error_msg = self.process_reset_payload(payload)

                    if error_msg:
                        # Processing failed, store error and pass through
                        msg[error_key] = error_msg
                        self.logger.error(f"Failed to process reset payload: {error_msg}")
                        print(
                            self.log_prefix(msg.get("ID", "unknown"))
                            + f"ERROR: {error_msg}"
                        )
                    else:
                        # Processing successful - extract reset information
                        msg[reset_id_key] = reset_id
                        msg[new_scenario_start_key] = new_scenario_start_time
                        msg[hard_reset_flag_key] = hard_reset_database

                        # Execute the simulation reset
                        reset_success = self.execute_simulation_reset(new_scenario_start_time, hard_reset_database)
                        msg[reset_complete_key] = reset_success

                        if reset_success:
                            # Clear any previous error
                            if error_key in msg:
                                del msg[error_key]

                            print(
                                self.log_prefix(msg.get("ID", "unknown"))
                                + f"Successfully processed simulation reset: {reset_id}, new start time: {new_scenario_start_time}, hard reset: {hard_reset_database}"
                            )
                        else:
                            msg[error_key] = "Failed to execute simulation reset"
                            print(
                                self.log_prefix(msg.get("ID", "unknown"))
                                + f"ERROR: Failed to execute simulation reset for {reset_id}"
                            )

                processing_time = self._processing_delay()
                data_out_list = [msg]
            else:
                data_out_list = []
