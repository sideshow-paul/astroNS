#!/usr/bin/env python3
"""
Test script to verify that pydantic_models imports work correctly
after moving the folder into the nodes directory.
"""

import sys
import os

# Add the astroNS source directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'astroNS'))

def test_pydantic_model_imports():
    """Test that pydantic models can be imported from new location"""
    
    print("Testing pydantic model imports from nodes.pydantic_models...")
    print("=" * 60)
    
    try:
        # Test individual model imports
        print("Testing individual model imports...")
        from nodes.pydantic_models.simulator_interfaces import TaskAssignment
        print("✓ TaskAssignment import successful")
        
        from nodes.pydantic_models.simulator_interfaces import SimulatorControlMessage
        print("✓ SimulatorControlMessage import successful")
        
        from nodes.pydantic_models.simulator_interfaces import CollectedTargetData
        print("✓ CollectedTargetData import successful")
        
        # Test ParseJsonMessage node import
        print("\nTesting ParseJsonMessage node import...")
        from nodes.pydantic_models.ParseJsonMessage import ParseJsonMessage
        print("✓ ParseJsonMessage import successful")
        
        # Test package-level imports
        print("\nTesting package-level imports...")
        from nodes.pydantic_models import TaskAssignment, SimulatorControlMessage, CollectedTargetData, ParseJsonMessage
        print("✓ Package-level imports successful")
        
        print("\nTesting object creation...")
        
        # Test TaskAssignment creation
        task_assignment = TaskAssignment(
            assignment_id="test-001",
            opportunity_id="opp-001",
            task_id="task-001",
            satellite_name="TEST-SAT",
            status="pending_simulation",
            target_id="target-001",
            aimpoint_latitude=40.7128,
            aimpoint_longitude=-74.0060,
            access_start_time_unix_ts=1687104000.0,
            access_end_time_unix_ts=1687107600.0
        )
        print("✓ TaskAssignment object creation successful")
        
        # Test SimulatorControlMessage creation
        control_message = SimulatorControlMessage(
            message_type="END_OF_ASSIGNMENT_BATCH_AND_ADVANCE_TIME",
            timestamp=1687104000.0
        )
        print("✓ SimulatorControlMessage object creation successful")
        
        # Test CollectedTargetData creation
        collected_data = CollectedTargetData(
            collected_target_data_id="data-001",
            assignment_id="assignment-001",
            opportunity_id=123,
            task_id=456,
            target_id=789,
            satellite_name="TEST-SAT",
            aimpoint_latitude=40.7128,
            aimpoint_longitude=-74.0060,
            collection_time_unix_ts=1687108000.0,
            simulated_success_status=True
        )
        print("✓ CollectedTargetData object creation successful")
        
        print("\n🎉 All pydantic model imports and object creation successful!")
        return True
        
    except ImportError as e:
        print(f"✗ Import Error: {e}")
        return False
    except Exception as e:
        print(f"✗ Error: {e}")
        return False

def test_nodes_package_import():
    """Test that nodes package imports work correctly"""
    
    print("\nTesting nodes package imports...")
    print("=" * 60)
    
    try:
        # Test importing from nodes package
        from nodes import pydantic_models
        print("✓ nodes.pydantic_models package import successful")
        
        # Test accessing classes through package
        TaskAssignment = pydantic_models.TaskAssignment
        ParseJsonMessage = pydantic_models.ParseJsonMessage
        print("✓ Accessing classes through package successful")
        
        # Test wildcard import
        from nodes.pydantic_models import *
        print("✓ Wildcard import successful")
        
        print("\n🎉 All nodes package imports successful!")
        return True
        
    except ImportError as e:
        print(f"✗ Import Error: {e}")
        return False
    except Exception as e:
        print(f"✗ Error: {e}")
        return False

def test_yaml_compatibility():
    """Test that YAML references still work"""
    
    print("\nTesting YAML compatibility...")
    print("=" * 60)
    
    # Simulate how YAML would reference the ParseJsonMessage node
    try:
        from nodes.pydantic_models import ParseJsonMessage
        
        # This simulates what the YAML loader would do
        node_class = ParseJsonMessage
        print("✓ ParseJsonMessage can be referenced for YAML loading")
        
        # Test that we can access the pydantic classes for type checking
        from nodes.pydantic_models import TaskAssignment, SimulatorControlMessage, CollectedTargetData
        print("✓ Pydantic classes accessible for type validation")
        
        print("\n🎉 YAML compatibility maintained!")
        return True
        
    except Exception as e:
        print(f"✗ YAML compatibility error: {e}")
        return False

if __name__ == "__main__":
    print("Pydantic Models Import Test")
    print("This script verifies that pydantic_models can be imported correctly")
    print("after moving to the nodes directory.\n")
    
    success1 = test_pydantic_model_imports()
    success2 = test_nodes_package_import()
    success3 = test_yaml_compatibility()
    
    if success1 and success2 and success3:
        print("\n🎉 All tests passed! Pydantic models imports are working correctly.")
        print("The pydantic_models folder has been successfully moved to nodes/pydantic_models")
        exit_code = 0
    else:
        print("\n❌ Some tests failed. Check the error messages above.")
        exit_code = 1
    
    sys.exit(exit_code)