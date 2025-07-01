""" Process Batch Payload node processes SimTaskBatchPayload and creates individual task messages.

This node takes a SimTaskBatchPayload from the input message and creates separate output
messages for each task in the batch. Each output message contains all fields from the
SimTaskRequestStructure as individual keys, plus the original SimTaskRequestStructure
object stored in a 'SimTaskRequest' key.

"""
from simpy.core import Environment
from typing import List, Dict, Tuple, Any, Optional, Callable
from datetime import datetime
import logging
import uuid

from nodes.core.base import BaseNode
from nodes.pydantic_models.two_six_messages import (
    SimTaskBatchPayload,
    SimTaskRequestStructure,
    CollectedTargetDataPayload
)


class ProcessBatchPayload(BaseNode):
    """ProcessBatchPayload class"""

    def __init__(self, env: Environment, name: str, configuration: Dict[str, Any]):
        """Initialize ProcessBatchPayload class"""
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
        self._error_key = self.setStringFromConfig("error_key", "batch_process_error")
        self._task_request_key = self.setStringFromConfig("task_request_key", "SimTaskRequest")
        self._preserve_original_message = self.setBoolFromConfig("preserve_original_message", True)
        self._batch_info_keys = configuration.get("batch_info_keys", ["agent_id", "time_step_end_time"])

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
    def task_request_key(self) -> Optional[str]:
        return self._task_request_key()

    @property
    def preserve_original_message(self) -> bool:
        return self._preserve_original_message()

    @property
    def batch_info_keys(self) -> List[str]:
        return self._batch_info_keys

    def create_task_message(self, task: SimTaskRequestStructure, batch_payload: SimTaskBatchPayload, original_message: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create an individual task message from a SimTaskRequestStructure.

        Args:
            task: SimTaskRequestStructure instance
            batch_payload: The original SimTaskBatchPayload
            original_message: The original input message

        Returns:
            Dictionary containing the task message
        """
        # Start with original message if preserving it
        if self.preserve_original_message:
            task_message = original_message.copy()
        else:
            task_message = {}

        # Generate unique ID for this task message
        task_message['ID'] = str(uuid.uuid4())

        # Add all SimTaskRequestStructure fields as individual keys
        task_message['task_id'] = task.task_id
        task_message['opportunity_id'] = task.opportunity_id
        task_message['original_task_id'] = task.original_task_id
        task_message['agent_id'] = task.agent_id
        task_message['satellite_id'] = task.satellite_id
        task_message['target_id'] = task.target_id
        task_message['start_time'] = task.start_time
        task_message['duration'] = task.duration
        task_message['priority'] = task.priority
        task_message['time_step_window'] = task.time_step_window
        task_message['task_type'] = task.task_type
        task_message['parameters'] = task.parameters

        # Store the complete SimTaskRequestStructure object
        task_message[self.task_request_key] = task

        # Add batch-level information
        for batch_key in self.batch_info_keys:
            if hasattr(batch_payload, batch_key):
                task_message[f"batch_{batch_key}"] = getattr(batch_payload, batch_key)

        return task_message

    def process_batch_payload(self, payload: Any) -> Tuple[List[Dict[str, Any]], Optional[str]]:
        """
        Process the SimTaskBatchPayload to create individual task messages.

        Args:
            payload: Expected to be SimTaskBatchPayload instance

        Returns:
            Tuple of (list_of_task_messages, error_message)
        """
        # Check if payload is the correct type
        if not isinstance(payload, SimTaskBatchPayload):
            return [], f"Invalid payload type: {type(payload)}. Expected SimTaskBatchPayload."

        try:
            task_messages = []

            # Check if there are tasks in the batch
            if not payload.tasks:
                return [], "No tasks found in the batch payload"

            # Process each task in the batch
            for i, task in enumerate(payload.tasks):
                if not isinstance(task, SimTaskRequestStructure):
                    self.logger.warning(f"Task {i} is not a SimTaskRequestStructure: {type(task)}")
                    continue

                # Create individual task message
                task_message = self.create_task_message(task, payload, {})
                task_messages.append(task_message)

            if not task_messages:
                return [], "No valid tasks found in the batch payload"

            return task_messages, None

        except Exception as e:
            return [], f"Error processing batch payload: {str(e)}"

    def execute(self):
        """Simpy execution code"""
        delay_till_get_next_msg: float = 0.0
        time_to_send_data_out: float = 0.0
        data_out_list: List[Dict[str, Any]] = []
        # delay_till_get_next_msg,time_to_send_data_out
        while True:
            data_in = yield (delay_till_get_next_msg, time_to_send_data_out, data_out_list)

            if data_in:
                msg = data_in.copy()
                delay_till_get_next_msg = self.time_delay
                #import pudb; pu.db
                # Get configuration values from input or defaults
                payload_key = msg.get('payload_key', self.payload_key)
                error_key = msg.get('error_key', self.error_key)
                task_request_key = msg.get('task_request_key', self.task_request_key)

                # Check if the payload key exists in the message
                if payload_key not in msg:
                    # Payload key not found, pass through unchanged
                    print(
                        self.log_prefix(msg.get("ID", "unknown"))
                        + f"Payload key '{payload_key}' not found in message, passing through unchanged"
                    )
                    data_out_list = [msg]
                else:
                    # Process the batch payload
                    payload = msg[payload_key]
                    task_messages, error_msg = self.process_batch_payload(payload)

                    if error_msg:
                        # Processing failed, store error and pass through original message
                        msg[error_key] = error_msg
                        self.logger.error(f"Failed to process batch payload: {error_msg}")
                        print(
                            self.log_prefix(msg.get("ID", "unknown"))
                            + f"ERROR: {error_msg}"
                        )
                        msg['tasking'] = 'None'
                        data_out_list = [msg]
                    else:
                        # Processing successful - create individual task messages
                        data_out_list = []
                        time_to_send_data_out = []
                        for i, task_message in enumerate(task_messages):
                            # Add original message context if preserving
                            if self.preserve_original_message:
                                # Copy relevant fields from original message (except payload)
                                for key, value in msg.items():
                                    if key != payload_key and key not in task_message:
                                        task_message[key] = value
                            #import pudb; pu.db
                            task = task_message['SimTaskRequest']
                            task_collect_datetime = task.start_time
                            task_simtime = self.env.now +(task_collect_datetime - self.env.now_datetime()).total_seconds()
                            # Clear any previous error
                            if error_key in task_message:
                                del task_message[error_key]


                            time_to_send_data_out.append(task_simtime)
                            task_message['tasking'] = task.task_id
                            data_out_list.append(task_message)

                        print(
                            self.log_prefix(msg.get("ID", "unknown"))
                            + f"Successfully processed batch payload: created {len(task_messages)} individual task messages"
                        )

                        # Log details about each task
                        for i, task_message in enumerate(task_messages):
                            task = task_message[task_request_key]
                            print(
                                self.log_prefix(task_message.get("ID", "unknown"))
                                + f"Task {i+1}: {task.task_id} for satellite {task.satellite_id}, target {task.target_id}, Simtime: {time_to_send_data_out[i]}"
                            )

                #time_to_send_data_out = self._processing_delay()
            else:
                data_out_list = []
