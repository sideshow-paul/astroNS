# Simulator Component: Pulsar Message Interface Definitions

This document outlines the JSON message formats for data flowing into and out of the **Simulator** component within the SixGeo project. These definitions are crucial for understanding how to interact with the Simulator via Apache Pulsar.

**Go Structs Reference:** The definitive Go language representations of these messages can be found in the project's `common/models/` directory (e.g., `github.com/twosixlabs/SixGeo/common/models/simulator_io_models.go`).

---

## 1. Input Message: `TaskAssignment`

* **Pulsar Topic:** `persistent://twosix/sixgeo/task-assignments`
    * *Configuration:* Simulator's `config.yaml` under `pulsar.consumer_topics.task_assignments`.
* **Purpose:** Sent by the Agent Framework to instruct the Simulator to simulate a specific collection task. This message includes denormalized (copied) details from the original `Opportunity` to make the Simulator more self-contained.
* **Consumed by:** Simulator
* **Produced by:** Agent Framework
* **Corresponding Go Struct:** `models.TaskAssignment`

### JSON Schema: `TaskAssignment`

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "TaskAssignment",
  "description": "Message instructing the Simulator to perform a collection task, including key opportunity details.",
  "type": "object",
  "properties": {
    "assignment_id": {
      "description": "Unique ID for this specific assignment instance (e.g., UUID string from Python agent).",
      "type": "string"
    },
    "opportunity_id": {
      "description": "ID of the opportunity being assigned (string representation of what might be a BIGSERIAL in the DB).",
      "type": "string"
    },
    "task_id": {
      "description": "ID of the original task (string representation of what might be a BIGSERIAL in the DB).",
      "type": "string"
    },
    "satellite_name": {
      "description": "Name of the satellite assigned for the collection.",
      "type": "string"
    },
    "assigned_by_agent_id": {
      "description": "ID of the agent that made this assignment.",
      "type": ["string", "null"]
    },
    "status": {
      "description": "Status of the assignment (e.g., 'pending_simulation').",
      "type": "string"
    },
    "target_id": {
      "description": "ID of the target for this collection (string representation of what might be a BIGSERIAL in the DB).",
      "type": "string"
    },
    "aimpoint_latitude": {
      "description": "Latitude of the aimpoint for the collection.",
      "type": "number",
      "format": "double"
    },
    "aimpoint_longitude": {
      "description": "Longitude of the aimpoint for the collection.",
      "type": "number",
      "format": "double"
    },
    "access_start_time_unix_ts": {
      "description": "Start of the collection access window (Unix timestamp, float seconds).",
      "type": "number",
      "format": "double"
    },
    "access_end_time_unix_ts": {
      "description": "End of the collection access window (Unix timestamp, float seconds).",
      "type": "number",
      "format": "double"
    },
    "predicted_value_at_assignment": {
      "description": "Predicted value of the opportunity at the time of assignment.",
      "type": ["number", "null"],
      "format": "double"
    },
    "predicted_cloud_cover_at_assignment": {
      "description": "Predicted cloud cover (0.0 to 1.0) at the time of assignment.",
      "type": ["number", "null"],
      "format": "double"
    },
    "mean_look_angle_at_assignment": {
      "description": "Mean look angle (degrees) for the opportunity at assignment.",
      "type": ["number", "null"],
      "format": "double"
    }
  },
  "required": [
    "assignment_id",
    "opportunity_id",
    "task_id",
    "satellite_name",
    "status",
    "target_id",
    "aimpoint_latitude",
    "aimpoint_longitude",
    "access_start_time_unix_ts",
    "access_end_time_unix_ts"
  ]
}
```

### JSON Example: `TaskAssignment`

```json
{
  "assignment_id": "assign_uuid_agent001_123",
  "opportunity_id": "101",
  "task_id": "55",
  "satellite_name": "SatAlpha",
  "assigned_by_agent_id": "python_agent_001",
  "status": "pending_simulation",
  "target_id": "203",
  "aimpoint_latitude": 34.0522,
  "aimpoint_longitude": -118.2437,
  "access_start_time_unix_ts": 1715889600.0,
  "access_end_time_unix_ts": 1715890200.0,
  "predicted_value_at_assignment": 85.5,
  "predicted_cloud_cover_at_assignment": 0.15,
  "mean_look_angle_at_assignment": 22.5
}
```

---

## 2. Input Message: `SimulatorControlMessage`

* **Pulsar Topic:** `persistent://twosix/sixgeo/simulator-control`
    * *Configuration:* Simulator's `config.yaml` under `pulsar.consumer_topics.simulator_control`.
* **Purpose:** Sent by the Agent Framework to signal the end of an assignment batch and to instruct the Simulator to advance its internal simulation time. This is the primary mechanism for managing simulation time progression.
* **Consumed by:** Simulator
* **Produced by:** Agent Framework
* **Corresponding Go Struct:** `models.SimulatorControlMessage`

### JSON Schema: `SimulatorControlMessage`

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "SimulatorControlMessage",
  "description": "Control message for the Simulator, primarily for triggering processing and time advancement.",
  "type": "object",
  "properties": {
    "message_type": {
      "description": "Type of control message (e.g., 'END_OF_ASSIGNMENT_BATCH_AND_ADVANCE_TIME').",
      "type": "string"
    },
    "timestamp": {
      "description": "Wall-clock Unix timestamp (float seconds) when the message was created by the agent.",
      "type": "number",
      "format": "double"
    },
    "batch_id": {
      "description": "Optional ID for the batch of assignments this control message corresponds to.",
      "type": ["string", "null"]
    },
    "advance_simulation_time_to_unix_ts": {
      "description": "Instructs the Simulator to advance its internal simulation time to this Unix timestamp (float seconds) after processing relevant tasks from the current batch.",
      "type": ["number", "null"],
      "format": "double"
    },
    "payload": {
      "description": "Optional additional key-value data for the control message.",
      "type": ["object", "null"],
      "additionalProperties": true
    }
  },
  "required": [
    "message_type",
    "timestamp"
  ]
}
```

### JSON Example: `SimulatorControlMessage`

```json
{
  "message_type": "END_OF_ASSIGNMENT_BATCH_AND_ADVANCE_TIME",
  "timestamp": 1715890800.5,
  "batch_id": "batch_agent001_cycle123",
  "advance_simulation_time_to_unix_ts": 1715892600.0
}
```

---

## 3. Output Message: `CollectedTargetData`

* **Pulsar Topic:** `persistent://twosix/sixgeo/collected-target-data`
    * *Configuration:* Simulator's `config.yaml` under `pulsar.producer_topic_collected_data`.
* **Purpose:** Produced by the Simulator after simulating a collection based on a `TaskAssignment`. This data is consumed by the `CollectEvaluator`.
* **Produced by:** Simulator
* **Consumed by:** CollectEvaluator
* **Corresponding Go Struct:** `models.CollectedTargetData`
* **Note on ID Types:** In this message, `OpportunityID`, `TaskID`, and `TargetID` are **numeric (int64)**. The Simulator converts these from the string format received in the `TaskAssignment` message to align with the `CollectEvaluator`'s database interaction expectations.

### JSON Schema: `CollectedTargetData`

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "CollectedTargetData",
  "description": "Output from the Simulator detailing the results of a simulated collection.",
  "type": "object",
  "properties": {
    "collected_target_data_id": {
      "description": "Unique ID for this collection data record (e.g., UUID string generated by Simulator).",
      "type": "string"
    },
    "assignment_id": {
      "description": "ID of the TaskAssignment that triggered this simulation (passed through).",
      "type": "string"
    },
    "opportunity_id": {
      "description": "ID of the original opportunity (numeric, int64).",
      "type": "integer"
    },
    "task_id": {
      "description": "ID of the original task (numeric, int64).",
      "type": "integer"
    },
    "target_id": {
      "description": "ID of the target (numeric, int64).",
      "type": "integer"
    },
    "satellite_name": {
      "description": "Name of the satellite that performed the simulated collection.",
      "type": "string"
    },
    "aimpoint_latitude": {
      "description": "Latitude of the aimpoint used for the simulation (passed through from TaskAssignment).",
      "type": "number",
      "format": "double"
    },
    "aimpoint_longitude": {
      "description": "Longitude of the aimpoint used for the simulation (passed through from TaskAssignment).",
      "type": "number",
      "format": "double"
    },
    "collection_time_unix_ts": {
      "description": "Simulated time of collection (Unix timestamp, float seconds).",
      "type": "number",
      "format": "double"
    },
    "simulated_success_status": {
      "description": "Boolean indicating if the simulated collection was successful.",
      "type": "boolean"
    },
    "failure_reason": {
      "description": "Reason for collection failure, if applicable (e.g., 'CLOUD_COVER', 'SENSOR_MALFUNCTION').",
      "type": ["string", "null"]
    },
    "simulated_quality_score": {
      "description": "Overall quality score of the simulated collection (e.g., 0.0 to 1.0, or NIIRS).",
      "type": ["number", "null"],
      "format": "double"
    },
    "simulated_gsd_cm": {
      "description": "Simulated Ground Sample Distance in centimeters.",
      "type": ["number", "null"],
      "format": "double"
    },
    "simulated_cloud_cover_percent": {
      "description": "Actual cloud cover percentage used or determined by the simulator (0.0 to 1.0).",
      "type": ["number", "null"],
      "format": "double"
    },
    "simulated_area_covered_sqkm": {
      "description": "Simulated area covered in square kilometers.",
      "type": ["number", "null"],
      "format": "double"
    },
    "additional_sim_metadata": {
      "description": "Optional key-value pairs for any other simulation-specific outputs.",
      "type": ["object", "null"],
      "additionalProperties": true
    },
    "notes_from_simulator": {
        "description": "General textual notes from the simulator regarding this collection.",
        "type": ["string", "null"]
    }
  },
  "required": [
    "collected_target_data_id",
    "assignment_id",
    "opportunity_id",
    "task_id",
    "target_id",
    "satellite_name",
    "aimpoint_latitude",
    "aimpoint_longitude",
    "collection_time_unix_ts",
    "simulated_success_status"
  ]
}
```

### JSON Example: `CollectedTargetData`

```json
{
  "collected_target_data_id": "col_7a9f3cbb-09f5-4e9a-8b2e-56d8f8a091e2",
  "assignment_id": "assign_uuid_agent001_123",
  "opportunity_id": 101,
  "task_id": 55,
  "target_id": 203,
  "satellite_name": "SatAlpha",
  "aimpoint_latitude": 34.0522,
  "aimpoint_longitude": -118.2437,
  "collection_time_unix_ts": 1715889900.0,
  "simulated_success_status": true,
  "failure_reason": null,
  "simulated_quality_score": 0.85,
  "simulated_gsd_cm": 50.5,
  "simulated_cloud_cover_percent": 0.10,
  "simulated_area_covered_sqkm": 100.0,
  "additional_sim_metadata": {
    "sensor_mode_used": "PAN_SHARPENED",
    "look_angle_achieved_deg": 22.1
  },
  "notes_from_simulator": "Nominal collection simulated successfully. Minor atmospheric haze."
}
```

---
