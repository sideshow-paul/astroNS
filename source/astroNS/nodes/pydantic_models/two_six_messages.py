"""
Pydantic models for SixGeo Simulator Pulsar Interface messages.

This module defines all message types for data flowing into and out of the
SixGeo Simulator component via Apache Pulsar.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, Field


# Enums for message types
class InputMessageType(str, Enum):
    """Valid message types for input messages to the Simulator."""
    TIME_ADVANCE = "time_advance"
    TASK_BATCH = "task_batch"


class OutputMessageType(str, Enum):
    """Valid message types for output messages from the Simulator."""
    SIMULATION_STEP_COMPLETE = "simulation_step_complete"
    COLLECTED_TARGET_DATA = "collected_target_data"


class SimulationStatus(str, Enum):
    """Status values for simulation step completion."""
    COMPLETED = "Completed"
    ERROR = "Error"


# Input Message Payloads (Consumed by Simulator)
class SimTimeAdvanceCommandPayload(BaseModel):
    """
    Payload for advancing simulation time.
    Origin: Agent Coordinator - Go
    """
    TimeStepStartTime: datetime = Field(..., description="ISO 8601 UTC timestamp")
    TimeStepEndTime: datetime = Field(..., description="ISO 8601 UTC timestamp")


class SimTaskRequestStructure(BaseModel):
    """
    Definition of a single task request within a batch.
    Origin: Agent Framework - Python
    """
    task_id: str = Field(..., description="Agent-generated unique ID for this task attempt")
    opportunity_id: str = Field(..., description="Original Opportunity ID")
    original_task_id: str = Field(..., description="Original database Task ID")
    agent_id: Optional[str] = Field(None, description="Agent ID responsible for this specific task")
    satellite_id: str = Field(..., description="Name/ID of the satellite")
    target_id: str = Field(..., description="Original Target ID")
    start_time: datetime = Field(..., description="Planned UTC start time of the task")
    duration: float = Field(..., description="Planned duration in seconds")
    priority: int = Field(..., description="Task priority")
    time_step_window: datetime = Field(..., description="The TimeStepEndTime this task is intended for")
    task_type: str = Field(default="image_collect", description="Type of task")
    parameters: Dict[str, Any] = Field(
        default_factory=dict,
        description="Key-value parameters, e.g., aimpoint_latitude, aimpoint_longitude"
    )


class SimTaskBatchPayload(BaseModel):
    """
    Payload for submitting a batch of tasks from an Agent.
    Origin: Agent Framework - Python
    """
    agent_id: str = Field(..., description="ID of the agent submitting the batch")
    tasks: List[SimTaskRequestStructure] = Field(..., description="List of task requests")
    time_step_end_time: datetime = Field(..., description="The TimeStepEndTime this entire batch is associated with")


# Output Message Payloads (Produced by Simulator)
class SimulationStepCompletePayload(BaseModel):
    """
    Signals the Simulator has completed processing up to a given time.
    Origin: Simulator - Go
    """
    TimeStepEndTime: datetime
    Status: SimulationStatus
    Message: Optional[str] = Field(None, description="Optional message, e.g., in case of an error")


class CollectedTargetDataPayload(BaseModel):
    """
    Detailed results of a simulated collection event.
    Origin: Simulator - Go
    Field names follow Go struct JSON output, typically snake_case due to tags or PascalCase if no tags.
    """
    collected_target_data_id: str = Field(..., description="Unique ID for this collection data record (UUID)")
    assignment_id: str = Field(..., description="Agent's original task_id for this attempt")
    opportunity_id: int
    task_id: int = Field(..., description="Original database Task ID")
    target_id: int
    satellite_name: str
    agent_id: str = Field(..., description="Agent who initiated the original task")
    actual_collection_start_time: datetime
    actual_collection_end_time: datetime
    aimpoint_latitude: float
    aimpoint_longitude: float
    simulated_success_status: bool
    failure_reason: Optional[str] = None
    simulated_quality_score: Optional[float] = None
    simulated_gsd_cm: Optional[float] = None
    simulated_cloud_cover_percent: Optional[float] = None
    simulated_area_covered_sqkm: Optional[float] = None
    collected_metrics: Optional[Dict[str, Any]] = Field(None, description="Additional metrics from the collection")
    additional_sim_metadata: Optional[Dict[str, Any]] = Field(None, description="Other simulation-specific metadata")
    notes_from_simulator: Optional[str] = Field(None, description="General notes from the simulator")


# Wrapper Schemas
class WrappedInputMessage(BaseModel):
    """Wrapper for messages sent TO the Simulator."""
    message_type: InputMessageType = Field(..., description="Discriminator for the payload type")
    payload: Union[SimTimeAdvanceCommandPayload, SimTaskBatchPayload] = Field(..., description="The actual message payload")

    class Config:
        """Pydantic configuration."""
        use_enum_values = True

    def get_payload_type(self) -> type:
        """Return the actual type of the payload based on message_type."""
        if self.message_type == InputMessageType.TIME_ADVANCE:
            return SimTimeAdvanceCommandPayload
        elif self.message_type == InputMessageType.TASK_BATCH:
            return SimTaskBatchPayload
        else:
            raise ValueError(f"Unknown message_type: {self.message_type}")


class WrappedOutputMessage(BaseModel):
    """Wrapper for messages sent FROM the Simulator."""
    message_type: OutputMessageType = Field(..., description="Discriminator for the payload type")
    payload: Union[SimulationStepCompletePayload, CollectedTargetDataPayload] = Field(
        ..., description="The actual message payload"
    )

    class Config:
        """Pydantic configuration."""
        use_enum_values = True

    def get_payload_type(self) -> type:
        """Return the actual type of the payload based on message_type."""
        if self.message_type == OutputMessageType.SIMULATION_STEP_COMPLETE:
            return SimulationStepCompletePayload
        elif self.message_type == OutputMessageType.COLLECTED_TARGET_DATA:
            return CollectedTargetDataPayload
        else:
            raise ValueError(f"Unknown message_type: {self.message_type}")


# Type aliases for clearer type hints
SimTimeAdvanceCommand = SimTimeAdvanceCommandPayload
SimTaskBatch = SimTaskBatchPayload
SimTaskRequest = SimTaskRequestStructure
SimulationStepComplete = SimulationStepCompletePayload
CollectedTargetData = CollectedTargetDataPayload