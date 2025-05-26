import sys
import os
import simpy
import json
from datetime import datetime

# Add source directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'astroNS'))

# Import the ParseJsonMessage node
from pydantic_models.ParseJsonMessage import ParseJsonMessage

class MockQueue:
    def __init__(self):
        self.items = []
    
    def get(self):
        if self.items:
            return self.items.pop(0)
        return None
    
    def put(self, item):
        self.items.append(item)

def test_parse_json_message_node():
    """Test the ParseJsonMessage node with different Pydantic types"""
    
    # Create SimPy environment
    env = simpy.Environment()
    env.in_queue = MockQueue()
    env.out_queue = MockQueue()
    
    # Configuration parameters
    config = {
        "json_key": "json_data",
        "pydantic_types": ["TaskAssignment", "SimulatorControlMessage", "CollectedTargetData"],
        "result_key": "parsed_object",
        "error_key": "parse_error",
        "successful_type_key": "successful_type",
        "write_out_field_list": ["assignment_id", "satellite_name", "target_id"],
        "preserve_json": True,
        "time_processing": 0.0,
        "time_delay": 0.1
    }
    
    # Create ParseJsonMessage node
    parser = ParseJsonMessage(
        env=env,
        name="test_json_parser",
        configuration=config
    )
    
    # Define a process to send test input messages
    def input_process():
        # Wait a bit to let the node initialize
        yield env.timeout(1)
        
        # Test Case 1: Valid TaskAssignment JSON
        task_assignment_json = {
            "assignment_id": "12345-abcde",
            "opportunity_id": "67890",
            "task_id": "54321",
            "satellite_name": "EXAMPLE-SAT-1",
            "assigned_by_agent_id": "agent_001",
            "status": "pending_simulation",
            "target_id": "98765",
            "aimpoint_latitude": 40.7128,
            "aimpoint_longitude": -74.0060,
            "access_start_time_unix_ts": 1687104000.0,
            "access_end_time_unix_ts": 1687107600.0,
            "predicted_value_at_assignment": 0.85,
            "predicted_cloud_cover_at_assignment": 0.15,
            "mean_look_angle_at_assignment": 25.5
        }
        
        valid_input = {
            "ID": "TEST_001",
            "json_data": json.dumps(task_assignment_json)
        }
        env.in_queue.put(valid_input)
        
        # Wait between inputs
        yield env.timeout(5)
        
        # Test Case 2: Valid SimulatorControlMessage JSON
        control_message_json = {
            "message_type": "END_OF_ASSIGNMENT_BATCH_AND_ADVANCE_TIME",
            "timestamp": 1687104000.0,
            "batch_id": "batch_001",
            "advance_simulation_time_to_unix_ts": 1687200000.0,
            "payload": {"additional_info": "test_payload"}
        }
        
        control_input = {
            "ID": "TEST_002",
            "json_data": json.dumps(control_message_json),
            "result_key": "control_message"
        }
        env.in_queue.put(control_input)
        
        # Wait between inputs
        yield env.timeout(5)
        
        # Test Case 3: Valid CollectedTargetData JSON
        collected_data_json = {
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
            "simulated_cloud_cover_percent": 0.08,
            "simulated_area_covered_sqkm": 25.4,
            "additional_sim_metadata": {"sensor": "optical", "mode": "high_res"},
            "notes_from_simulator": "Collection completed successfully"
        }
        
        collected_input = {
            "ID": "TEST_003",
            "json_data": json.dumps(collected_data_json),
            "result_key": "collected_data"
        }
        env.in_queue.put(collected_input)
        
        # Wait between inputs
        yield env.timeout(5)
        
        # Test Case 4: Invalid JSON (should cause error)
        invalid_input = {
            "ID": "TEST_004",
            "json_data": "{ invalid json syntax }"
        }
        env.in_queue.put(invalid_input)
        
        # Wait between inputs
        yield env.timeout(5)
        
        # Test Case 5: Missing required field (should cause validation error)
        incomplete_json = {
            "assignment_id": "incomplete_test",
            # Missing required fields
        }
        
        incomplete_input = {
            "ID": "TEST_005",
            "json_data": json.dumps(incomplete_json)
        }
        env.in_queue.put(incomplete_input)
        
        # Wait between inputs
        yield env.timeout(5)
        
        # Test Case 6: Unknown pydantic type (should pass through)
        unknown_type_input = {
            "ID": "TEST_006",
            "json_data": json.dumps(task_assignment_json),
            "pydantic_types": ["UnknownType", "AnotherUnknownType"]
        }
        env.in_queue.put(unknown_type_input)
        
        # Wait between inputs
        yield env.timeout(5)
        
        # Test Case 7: Missing JSON key (should pass through)
        missing_json_input = {
            "ID": "TEST_007",
            "some_other_data": "test_data"
            # Missing json_data key
        }
        env.in_queue.put(missing_json_input)
        
        # Wait between inputs
        yield env.timeout(5)
        
        # Test Case 8: Mixed valid/invalid types in list
        mixed_types_input = {
            "ID": "TEST_008",
            "json_data": json.dumps(task_assignment_json),
            "pydantic_types": ["UnknownType", "TaskAssignment", "AnotherUnknown"]
        }
        env.in_queue.put(mixed_types_input)
        
        # Wait between inputs
        yield env.timeout(5)
        
        # Test Case 9: Write out all fields
        all_fields_input = {
            "ID": "TEST_009",
            "json_data": json.dumps(task_assignment_json),
            "write_out_field_list": "All Fields"
        }
        env.in_queue.put(all_fields_input)
        
        # Wait between inputs
        yield env.timeout(5)
        
        # Test Case 10: Write out specific fields only
        specific_fields_input = {
            "ID": "TEST_010",
            "json_data": json.dumps(control_message_json),
            "pydantic_types": ["SimulatorControlMessage"],
            "write_out_field_list": ["message_type", "timestamp", "batch_id"]
        }
        env.in_queue.put(specific_fields_input)
    
    # Define a process to read output from the node
    def output_process():
        while True:
            # Wait until we have output data
            yield env.timeout(2)
            
            # Check if there are results
            if env.out_queue.items:
                output_data = env.out_queue.items.pop(0)
                
                print(f"ID: {output_data.get('ID', 'unknown')}")
                
                # Check for parsed object
                if "parsed_object" in output_data:
                    parsed_obj = output_data["parsed_object"]
                    successful_type = output_data.get("successful_type", "Unknown")
                    print(f"Successfully parsed: {type(parsed_obj).__name__}")
                    print(f"Successful pydantic type: {successful_type}")
                    print(f"Object attributes: {list(parsed_obj.__dict__.keys())}")
                    
                    # Show some key attributes based on type
                    if hasattr(parsed_obj, 'assignment_id'):
                        print(f"  Assignment ID: {parsed_obj.assignment_id}")
                    if hasattr(parsed_obj, 'satellite_name'):
                        print(f"  Satellite: {parsed_obj.satellite_name}")
                    if hasattr(parsed_obj, 'message_type'):
                        print(f"  Message Type: {parsed_obj.message_type}")
                    if hasattr(parsed_obj, 'simulated_success_status'):
                        print(f"  Success: {parsed_obj.simulated_success_status}")
                
                # Check for alternative result keys
                for key in ["control_message", "collected_data"]:
                    if key in output_data:
                        parsed_obj = output_data[key]
                        successful_type = output_data.get("successful_type", "Unknown")
                        print(f"Successfully parsed {key}: {type(parsed_obj).__name__}")
                        print(f"Successful pydantic type: {successful_type}")
                
                # Check for errors
                if "parse_error" in output_data:
                    print(f"Parse Error: {output_data['parse_error']}")
                
                # Check if message was passed through unchanged
                if "some_other_data" in output_data:
                    print(f"Message passed through unchanged: {output_data.get('some_other_data')}")
                
                # Check for copied pydantic fields
                copied_fields = []
                pydantic_fields = ["assignment_id", "satellite_name", "target_id", "message_type", "timestamp", "batch_id", "opportunity_id", "task_id"]
                for field in pydantic_fields:
                    if field in output_data and field not in ["parsed_object", "control_message", "collected_data"]:
                        copied_fields.append(f"{field}: {output_data[field]}")
                
                if copied_fields:
                    print(f"Copied pydantic fields: {', '.join(copied_fields)}")
                
                # Check if original JSON was preserved
                if "json_data" in output_data:
                    print(f"Original JSON preserved: Yes")
                else:
                    print(f"Original JSON preserved: No")
                
                print("-" * 50)
    
    # Add processes to the environment
    env.process(input_process())
    env.process(output_process())
    
    # Run the simulation
    env.run(until=50)

if __name__ == "__main__":
    test_parse_json_message_node()