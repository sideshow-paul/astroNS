# SixGeoApp Time-Synchronized Messaging Scheme

This document outlines the Pulsar-based messaging scheme used for time synchronization and data flow between the core components of the SixGeoApp: `AgentCoordinator`, `AgentFramework`, `Simulator`, `CollectEvaluator`, and `OppStoreMonitor`.

## I. Global System Initialization

### 1. Message: `SystemParameters`

* **Producer:** `AgentCoordinator` (TimeSyncService)
* **Topic (from `agentcoordinator/config.yaml` -> `timesync.system_parameters_topic`):**
    `persistent://twosix/sixgeo/system_parameters_topic` (Example, confirm exact from your config)
* **Consumer(s):**
    * `AgentFramework` (MainLoop, on startup)
    * `OppStoreMonitor` (on startup)
    * `Simulator` (Optional, if it needs to align its `InitialSimTime` centrally)
* **Purpose:** To broadcast the scenario's absolute start time and standard time step durations to all relevant services.
* **Go Struct (`common/models/models.go`):**
    ```go
    type SystemParameters struct {
        ScenarioStartTime         time.Time `json:"scenario_start_time"`
        InitialTimeStepDuration   int64     `json:"initial_time_step_duration_seconds"`
        DefaultTimeStepDuration   int64     `json:"default_time_step_duration_seconds"`
    }
    ```
* **Python Class (`agentframework/data_models.py`):**
    ```python
    @dataclass
    class SystemParameters:
        scenario_start_time: str # ISO 8601 UTC string
        initial_time_step_duration_seconds: int
        default_time_step_duration_seconds: int
    ```
* **Flow:** `AgentCoordinator` publishes this once on startup after reading its own configuration. Other services consume it to initialize their time context.

---

## II. Agent Coordinator (`agentcoordinator`)

### Consumes:

1.  **Message:** `AgentStatus`
    * **Topic (from `agentcoordinator/config.yaml` -> `timesync.agent_status_topic`):**
        `persistent://twosix/sixgeo/agent_status_topic`
    * **Producer:** `AgentFramework`
    * **Purpose:** To register agents as "ONLINE" or "OFFLINE", allowing the coordinator to maintain a list of active agents.
    * **Go Struct (`common/models/models.go`):**
        ```go
        type AgentStatus struct {
            AgentID   string    `json:"agent_id"`
            Status    string    `json:"status"` // "ONLINE", "OFFLINE"
            Timestamp time.Time `json:"timestamp"`
        }
        ```

2.  **Message:** `AgentReadyForTimeStep`
    * **Topic (from `agentcoordinator/config.yaml` -> `pulsar.topics.agent_ready_topic`):**
        `persistent://twosix/sixgeo/agent_ready_topic`
    * **Producer:** `AgentFramework`
    * **Purpose:** Signals that an agent has completed its planning and task batch submission for the current time step.
    * **Go Struct (`common/models/models.go`):**
        ```go
        type AgentReadyForTimeStep struct {
            AgentID         string    `json:"agent_id"`
            TimeStepEndTime time.Time `json:"time_step_end_time"` // The end time of the step the agent is ready for
        }
        ```

3.  **Message:** `SimulationStepComplete`
    * **Topic (from `agentcoordinator/config.yaml` -> `pulsar.topics.sim_step_complete_topic`):**
        `persistent://twosix/sixgeo/sim_step_complete_topic`
    * **Producer:** `Simulator`
    * **Purpose:** Signals that the simulator has finished processing all tasks up to the commanded `TimeStepEndTime`.
    * **Go Struct (`common/models/models.go`):**
        ```go
        type SimulationStepComplete struct {
            TimeStepEndTime time.Time `json:"time_step_end_time"`
            Status          string    `json:"status"` // e.g., "Completed", "Error"
            Message         string    `json:"message,omitempty"`
        }
        ```

### Produces:

1.  **Message:** `SystemParameters` (Described in Section I)
    * **Topic:** `system_parameters_topic`
    * **Consumer(s):** `AgentFramework`, `OppStoreMonitor`, `Simulator` (optional)

2.  **Message:** `PlannerProceedSignal`
    * **Topic (from `agentcoordinator/config.yaml` -> `pulsar.topics.planner_proceed_signal_topic`):**
        `persistent://twosix/sixgeo/planner_proceed_signal_topic`
    * **Consumer:** `AgentFramework`
    * **Purpose:** To authorize agents to start their planning cycle for the next time step.
    * **Go Struct (`common/models/models.go`):**
        ```go
        type PlannerProceedSignal struct {
            NextTimeStepStartTime time.Time `json:"next_time_step_start_time"`
        }
        ```

3.  **Message:** `SimTimeAdvanceCommand`
    * **Topic (from `agentcoordinator/config.yaml` -> `pulsar.topics.sim_time_advance_command_topic`):**
        `persistent://twosix/sixgeo/sim_time_advance_topic`
    * **Consumer:** `Simulator`
    * **Purpose:** To authorize the simulator to run its simulation for a specific time window.
    * **Go Struct (`common/models/models.go`):**
        ```go
        type SimTimeAdvanceCommand struct {
            TimeStepStartTime time.Time `json:"time_step_start_time"`
            TimeStepEndTime   time.Time `json:"time_step_end_time"`
        }
        ```

---

## III. Agent Framework (`agentframework`)

### Consumes:

1.  **Message:** `SystemParameters`
    * **Topic (from `agentframework/config.yaml` -> `pulsar.system_parameters_topic`):**
        `persistent://twosix/sixgeo/system_parameters_topic` 
    * **Producer:** `AgentCoordinator`
    * **Purpose:** To learn the `ScenarioStartTime` and default step durations.
    * **Python Class (`agentframework/data_models.py`):** (Described in Section I)

2.  **Message:** `PlannerProceedSignal`
    * **Topic (from `agentframework/config.yaml` -> `pulsar.planner_proceed_signal_topic`):**
        `persistent://twosix/sixgeo/planner_proceed_signal_topic`
    * **Producer:** `AgentCoordinator`
    * **Purpose:** Triggers the agent to start its planning cycle for the indicated `NextTimeStepStartTime`.
    * **Python Class (`agentframework/data_models.py`):**
        ```python
        @dataclass
        class PlannerProceedSignal:
            next_time_step_start_time: str # ISO 8601 UTC string
        ```

3.  **Message:** `EvaluationCompleteNotice` (or your `EvaluatedCollectNotification`)
    * **Topic (from `agentframework/config.yaml` -> `pulsar.evaluation_notices_topic`):**
        `persistent://twosix/sixgeo/evaluation-completion-notices`
    * **Producer:** `CollectEvaluator`
    * **Purpose:** To inform the agent about the outcome of a specific task it scheduled.
    * **Python Class (`agentframework/data_models.py`):**
        ```python
        # Assuming Pydantic model as per your logs
        class EvaluationCompleteNotice(BaseModel): # Or your dataclass EvaluatedCollectNotification
            task_id: str # This must match the agent-generated SimTaskRequest.task_id
            agent_id: str
            collection_time: str # ISO 8601 UTC string
            evaluation_score: float
            evaluation_status: str
            evaluation_feedback: Optional[str] = None
        ```

### Produces:

1.  **Message:** `AgentStatus`
    * **Topic (from `agentframework/config.yaml` -> `pulsar.agent_status_topic`):**
        `persistent://twosix/sixgeo/agent_status_topic`
    * **Consumer:** `AgentCoordinator`
    * **Purpose:** To register "ONLINE" / "OFFLINE".
    * **Python Class (`agentframework/data_models.py`):** (Described in Section II)

2.  **Message:** `SimTaskBatch`
    * **Topic (from `agentframework/config.yaml` -> `pulsar.sim_task_batch_topic`):**
        `persistent://twosix/sixgeo/sim_task_batch_topic`
    * **Consumer:** `Simulator`
    * **Purpose:** To send planned and claimed tasks for the current time step to the simulator.
    * **Python Class (`agentframework/data_models.py`):**
        ```python
        @dataclass
        class SimTaskRequest: # Python definition
            task_id: str; opportunity_id: str; original_task_id: str; agent_id: str
            satellite_id: str; target_id: str; start_time: str; end_time: str
            duration: float; priority: int; time_step_window: str # ISO string
            task_type: str = "image_collect"; parameters: Optional[Dict[str, Any]] = field(default_factory=dict)
        @dataclass
        class SimTaskBatch:
            agent_id: str; tasks: List[SimTaskRequest]; time_step_end_time: str # ISO string
        ```

3.  **Message:** `AgentReadyForTimeStep`
    * **Topic (from `agentframework/config.yaml` -> `pulsar.agent_ready_topic`):**
        `persistent://twosix/sixgeo/agent_ready_topic`
    * **Consumer:** `AgentCoordinator`
    * **Purpose:** To signal completion of planning and task submission for the current step.
    * **Python Class (`agentframework/data_models.py`):** (Described in Section II)

---

## IV. Simulator (`simulator`)

### Consumes:

1.  **Message:** `SimTaskBatch`
    * **Topic (from `cmd/simulator/config.yaml` -> `Pulsar.SimTaskBatchTopic`):**
        `persistent://twosix/sixgeo/sim_task_batch_topic`
    * **Producer:** `AgentFramework`
    * **Purpose:** Receives tasks to be simulated.
    * **Go Struct (`common/models/models.go`):** (Described in Section II)

2.  **Message:** `SimTimeAdvanceCommand`
    * **Topic (from `cmd/simulator/config.yaml` -> `Pulsar.SimTimeAdvanceCommandTopic`):**
        `persistent://twosix/sixgeo/sim_time_advance_topic`
    * **Producer:** `AgentCoordinator`
    * **Purpose:** Authorization to start/continue simulation for a specific time window.
    * **Go Struct (`common/models/models.go`):** (Described in Section II)

### Produces:

1.  **Message:** `CollectedTargetData` (This is the logical "CollectionEvent")
    * **Topic (from `cmd/simulator/config.yaml` -> `Pulsar.CollectEvalInputTopic`):**
        `persistent://twosix/sixgeo/collect_eval_input_topic` (Ensure this matches CollectEvaluator's input)
    * **Consumer:** `CollectEvaluator`
    * **Purpose:** To report details of a simulated collection event.
    * **Go Struct (`common/models/models.go`):**
        ```go
        type CollectedTargetData struct {
            AssignmentID               string    `json:"assignment_id"` // Agent's SimTaskRequest.task_id
            TaskID                     int64     `json:"task_id"`       // Original DB TaskID
            OpportunityID              int64     `json:"opportunity_id"`
            AgentID                    string    `json:"agent_id"`
            SatelliteName              string    `json:"satellite_name"`
            TargetID                   int64     `json:"target_id"`
            ActualCollectionStartTime  time.Time `json:"actual_collection_start_time"`
            ActualCollectionEndTime    time.Time `json:"actual_collection_end_time"`
            SimulatedSuccessStatus     bool      `json:"simulated_success_status"`
            FailureReason              *string   `json:"failure_reason,omitempty"`
            CollectedMetrics           map[string]interface{} `json:"collected_metrics,omitempty"`
            SimulatedGSDCM             *float64  `json:"simulated_gsd_cm,omitempty"`
            AimpointLatitude           float64   `json:"aimpoint_latitude,omitempty"`
            AimpointLongitude          float64   `json:"aimpoint_longitude,omitempty"`
            CollectedTargetDataID      string    `json:"collected_target_data_id"` // Simulator generated UUID
            CollectionTimeUnixTS       float64   `json:"collection_time_unix_ts"`
            SimulatedQualityScore      *float64  `json:"simulated_quality_score,omitempty"`
            SimulatedCloudCoverPercent *float64  `json:"simulated_cloud_cover_percent,omitempty"`
            SimulatedAreaCoveredSqkm   *float64  `json:"simulated_area_covered_sqkm,omitempty"`
            AdditionalSimMetadata      map[string]interface{} `json:"additional_sim_metadata,omitempty"`
            NotesFromSimulator         *string   `json:"notes_from_simulator,omitempty"`
        }
        ```

2.  **Message:** `SimulationStepComplete`
    * **Topic (from `cmd/simulator/config.yaml` -> `Pulsar.SimStepCompleteTopic`):**
        `persistent://twosix/sixgeo/sim_step_complete_topic`
    * **Consumer:** `AgentCoordinator`
    * **Purpose:** To notify that the current simulation time step has been fully processed.
    * **Go Struct (`common/models/models.go`):** (Described in Section II)

---

## V. Collect Evaluator (`collectevaluator`)

### Consumes:

1.  **Message:** `CollectedTargetData`
    * **Topic (from `cmd/collectevaluator/config.yaml` -> `Pulsar.Topics.CollectedTargetData`):**
        `persistent://twosix/sixgeo/collected-data` (Ensure this matches Simulator's output topic)
    * **Producer:** `Simulator`
    * **Purpose:** Receives data about simulated collections for evaluation.
    * **Go Struct (`common/models/models.go`):** (Described in Section IV)

### Produces:

1.  **Message:** `EvaluatedCollectNotification`
    * **Topic (from `cmd/collectevaluator/config.yaml` -> `Pulsar.Topics.EvaluationCompleteNotices`):**
        `persistent://twosix/sixgeo/evaluation-completion-notices`
    * **Consumer:** `AgentFramework`
    * **Purpose:** To send the results of the collection evaluation back to the agent.
    * **Go Struct (`common/models/models.go`):**
        ```go
        type EvaluatedCollectNotification struct {
	        TaskID             string    `json:"task_id"`           // Should match SimTaskRequest.task_id / CollectedTargetData.AssignmentID
            AgentID            string    `json:"agent_id"`          // To help route to the correct agent if a central AF topic is used
            CollectionTime     time.Time `json:"collection_time"`
            EvaluationScore    float64   `json:"evaluation_score"`
            EvaluationStatus   string    `json:"evaluation_status"` // e.g., "CONFIRMED_COLLECT", "REJECTED_COLLECT"
            EvaluationFeedback string    `json:"evaluation_feedback,omitempty"`
        }
        ```
    *(Other messages like `MeasuredCollectionValue` and `TaskUpdates` are also produced by `CollectEvaluator` but are not part of this primary time-sync feedback loop to the agent).*

---

## VI. Opportunity Store Monitor (`oppstoremonitor`)

### Consumes:

1.  **Message:** `SystemParameters`
    * **Topic (from `oppstoremonitor/config.yaml` -> `pulsar.system_parameters_topic`):**
        `persistent://twosix/sixgeo/system_parameters_topic` (Confirm this matches AC's producer topic, e.g., `persistent://twosix/sixgeo/...`)
    * **Producer:** `AgentCoordinator`
    * **Purpose:** To learn the `ScenarioStartTime` to correctly define absolute time windows for opportunity generation requests.
    * **Go Struct (`common/models/models.go`):** (Described in Section I)

2.  **Message (Optional):** `SimulationStepComplete`
    * **Topic (from `oppstoremonitor/config.yaml` -> `pulsar.sim_step_complete_topic`):**
        `persistent://twosix/sixgeo/sim_step_complete_topic`
    * **Producer:** `Simulator`
    * **Purpose:** To reactively trigger opportunity generation as simulation time progresses.
    * **Go Struct (`common/models/models.go`):** (Described in Section II)

### Produces:

1.  **Message:** `OpGenTrigger`
    * **Topic (from `oppstoremonitor/config.yaml` -> `pulsar.opgen_trigger_topic`):**
        `persistent://twosix/sixgeo/opgen-trigger`
    * **Consumer:** `OpportunityGenerator`
    * **Purpose:** To instruct `OpportunityGenerator` to calculate and store opportunities for a specific absolute time window.
    * **Go Struct (`common/models/models.go`):**
        ```go
        type OpGenTrigger struct {
            TriggerID                   string    `json:"trigger_id"`
            TargetGenerationWindowStart time.Time `json:"target_generation_window_start"` // Absolute UTC
            TargetGenerationWindowEnd   time.Time `json:"target_generation_window_end"`   // Absolute UTC
            Reason                      *string   `json:"reason,omitempty"`
        }
        ```

---

This documentation covers the primary messages and topics involved in the time synchronization loop. 