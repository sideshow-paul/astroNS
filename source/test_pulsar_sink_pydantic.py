#!/usr/bin/env python3
"""
Test script for PulsarTopicSink pydantic functionality.
This script demonstrates how the sink can validate and transform data using Pydantic models.
"""

import sys
import os
import simpy
import json
from datetime import datetime, timezone

# Add source directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'astroNS'))

# Import the PulsarTopicSink node
from nodes.core.message_sinks.pulsarSink import PulsarTopicSink

class MockEnvironment:
    """Mock SimPy environment for testing"""
    def __init__(self):
        self.now = 0.0
        self._start_time = datetime.now(timezone.utc)
    
    def timeout(self, delay):
        self.now += delay
        return delay
    
    def now_datetime(self):
        return self._start_time.replace(microsecond=int((self.now % 1) * 1000000))
    
    def process(self, generator):
        # Mock process method
        pass

def test_pydantic_sink_functionality():
    """Test PulsarTopicSink with different pydantic configurations"""
    
    print("Testing PulsarTopicSink Pydantic Functionality")
    print("=" * 60)
    
    # Test configurations
    test_configs = [
        {
            "name": "No Pydantic Validation",
            "config": {
                "pulsar_server": "pulsar://localhost:6650",
                "topic_name": "test-no-validation",
                "use_pydantic_validation": False
            }
        },
        {
            "name": "CollectedTargetData Validation",
            "config": {
                "pulsar_server": "pulsar://localhost:6650", 
                "topic_name": "test-collected-data",
                "use_pydantic_validation": True,
                "pydantic_class": "CollectedTargetData"
            }
        },
        {
            "name": "TaskAssignment Validation",
            "config": {
                "pulsar_server": "pulsar://localhost:6650",
                "topic_name": "test-task-assignment",
                "use_pydantic_validation": True,
                "pydantic_class": "TaskAssignment"
            }
        },
        {
            "name": "SimulatorControlMessage Validation",
            "config": {
                "pulsar_server": "pulsar://localhost:6650",
                "topic_name": "test-control-message",
                "use_pydantic_validation": True,
                "pydantic_class": "SimulatorControlMessage"
            }
        }
    ]
    
    # Test data samples
    test_data = {
        "CollectedTargetData": {
            "ID": "data-001",
            "collected_target_data_id": "data_12345",
            "assignment_id": "assignment_67890",
            "opportunity_id": 123,
            "task_id": 456,
            "target_id": 789,
            "satellite_name": "TEST-SAT",
            "aimpoint_latitude": 35.6762,
            "aimpoint_longitude": 139.6503,
            "collection_time_unix_ts": 1687108000.0,
            "simulated_success_status": True,
            "simulated_quality_score": 0.92,
            "simulated_gsd_cm": 15.5,
            "extra_field": "This should be filtered out"
        },
        "TaskAssignment": {
            "ID": "task-001",
            "assignment_id": "12345-abcde",
            "opportunity_id": "67890",
            "task_id": "54321",
            "satellite_name": "EXAMPLE-SAT-1",
            "status": "pending_simulation",
            "target_id": "98765",
            "aimpoint_latitude": 40.7128,
            "aimpoint_longitude": -74.0060,
            "access_start_time_unix_ts": 1687104000.0,
            "access_end_time_unix_ts": 1687107600.0,
            "extra_simulation_data": "This should be filtered out"
        },
        "SimulatorControlMessage": {
            "ID": "control-001",
            "message_type": "END_OF_ASSIGNMENT_BATCH_AND_ADVANCE_TIME",
            "timestamp": 1687104000.0,
            "batch_id": "batch_001",
            "advance_simulation_time_to_unix_ts": 1687200000.0,
            "payload": {"additional_info": "test_payload"},
            "random_extra_field": "This should be filtered out"
        }
    }
    
    for config_test in test_configs:
        print(f"\nTesting: {config_test['name']}")
        print("-" * 40)
        
        try:
            # Create mock environment
            env = MockEnvironment()
            
            # Create PulsarTopicSink (will fail to connect to Pulsar but that's OK for testing)
            config = config_test['config']
            print(f"Configuration: {config}")
            
            # We'll simulate the sink's pydantic functionality without actual Pulsar connection
            sink = PulsarTopicSink(env, "test_sink", config)
            
            # Test pydantic object creation if validation is enabled
            if config.get('use_pydantic_validation', False):
                pydantic_class = config.get('pydantic_class')
                if pydantic_class in test_data:
                    test_input = test_data[pydantic_class]
                    print(f"Testing with {pydantic_class} data:")
                    print(f"Input data keys: {list(test_input.keys())}")
                    
                    # Test the _create_pydantic_object method
                    pydantic_obj = sink._create_pydantic_object(test_input)
                    
                    if pydantic_obj:
                        validated_data = pydantic_obj.model_dump()
                        print(f"✓ Pydantic validation successful")
                        print(f"Output data keys: {list(validated_data.keys())}")
                        print(f"Filtered out keys: {set(test_input.keys()) - set(validated_data.keys())}")
                        
                        # Show some key fields
                        if hasattr(pydantic_obj, 'assignment_id'):
                            print(f"Assignment ID: {pydantic_obj.assignment_id}")
                        if hasattr(pydantic_obj, 'satellite_name'):
                            print(f"Satellite: {pydantic_obj.satellite_name}")
                        if hasattr(pydantic_obj, 'message_type'):
                            print(f"Message Type: {pydantic_obj.message_type}")
                    else:
                        print("✗ Pydantic validation failed")
                else:
                    print(f"No test data available for {pydantic_class}")
            else:
                print("✓ No pydantic validation configured - data passes through unchanged")
                
        except Exception as e:
            print(f"✗ Error during test: {e}")
    
    print(f"\n🎯 CONFIGURATION EXAMPLES")
    print("=" * 60)
    
    # Show YAML configuration examples
    yaml_examples = [
        {
            "name": "Basic Sink (No Validation)",
            "yaml": """ProductDelivery:
  type: PulsarTopicSink
  topic_name: sim_output
  pulsar_server: pulsar://localhost:6650
  time_delay: 1"""
        },
        {
            "name": "Validated CollectedTargetData Output",
            "yaml": """ProductDelivery:
  type: PulsarTopicSink
  topic_name: collected_target_data
  pulsar_server: pulsar://localhost:6650
  use_pydantic_validation: true
  pydantic_class: CollectedTargetData
  time_delay: 1"""
        },
        {
            "name": "Validated TaskAssignment Output",
            "yaml": """TaskOutput:
  type: PulsarTopicSink
  topic_name: task_assignments_output
  pulsar_server: pulsar://localhost:6650
  use_pydantic_validation: true
  pydantic_class: TaskAssignment
  time_delay: 1"""
        }
    ]
    
    for example in yaml_examples:
        print(f"\n{example['name']}:")
        print(example['yaml'])

if __name__ == "__main__":
    try:
        test_pydantic_sink_functionality()
        
        print("\n🎉 SUMMARY")
        print("=" * 60)
        print("PulsarTopicSink now supports:")
        print("• Optional Pydantic validation before sending")
        print("• Automatic field filtering (removes non-model fields)")
        print("• Data validation and type conversion")
        print("• Graceful fallback if validation fails")
        print("• Support for all simulator interface models")
        
    except KeyboardInterrupt:
        print("\nTest interrupted by user")
    except Exception as e:
        print(f"Test failed with error: {e}")