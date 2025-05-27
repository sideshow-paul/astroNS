import sys
import os
import simpy
from datetime import datetime, timezone, timedelta

# Add source directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'astroNS'))

# Import the CalculateGeometry node
from nodes.aerospace.calculate_geometry import CalculateGeometry

class MockQueue:
    def __init__(self):
        self.items = []
    
    def get(self):
        if self.items:
            return self.items.pop(0)
        return None
    
    def put(self, item):
        self.items.append(item)

def test_satellite_name_key_scenarios():
    """Test different satellite_name_key configuration scenarios"""
    
    print("Testing CalculateGeometry satellite_name_key Configuration")
    print("=" * 70)
    
    test_scenarios = [
        {
            "name": "Standard satellite_name field",
            "config": {
                "satellite_name": "ISS",
                "satellite_name_key": "satellite_name",
                "tle_file_path": "data/satellites.json"
            },
            "message": {
                "ID": "TEST_001",
                "satellite_name": "HUBBLE",
                "aimpoint_latitude": 40.7128,
                "aimpoint_longitude": -74.0060
            },
            "expected_satellite": "HUBBLE"
        },
        {
            "name": "Custom spacecraft_id field",
            "config": {
                "satellite_name": "ISS",
                "satellite_name_key": "spacecraft_id",
                "tle_file_path": "data/satellites.json"
            },
            "message": {
                "ID": "TEST_002",
                "spacecraft_id": "TERRA",
                "aimpoint_latitude": 35.6762,
                "aimpoint_longitude": 139.6503
            },
            "expected_satellite": "TERRA"
        },
        {
            "name": "Custom vehicle_name field",
            "config": {
                "satellite_name": "ISS", 
                "satellite_name_key": "vehicle_name",
                "tle_file_path": "data/satellites.json"
            },
            "message": {
                "ID": "TEST_003",
                "vehicle_name": "LANDSAT8",
                "aimpoint_latitude": 51.5074,
                "aimpoint_longitude": -0.1278
            },
            "expected_satellite": "LANDSAT8"
        },
        {
            "name": "Missing satellite field (use default)",
            "config": {
                "satellite_name": "AQUA",
                "satellite_name_key": "satellite_name",
                "tle_file_path": "data/satellites.json"
            },
            "message": {
                "ID": "TEST_004",
                # No satellite_name field
                "aimpoint_latitude": -33.8688,
                "aimpoint_longitude": 151.2093
            },
            "expected_satellite": "AQUA"
        },
        {
            "name": "TaskAssignment format",
            "config": {
                "satellite_name": "ISS",
                "satellite_name_key": "satellite_name",
                "tle_file_path": "data/satellites.json"
            },
            "message": {
                "ID": "TEST_005",
                "assignment_id": "12345-abcde",
                "satellite_name": "WORLDVIEW3",
                "target_id": "target_001",
                "aimpoint_latitude": 48.8566,
                "aimpoint_longitude": 2.3522,
                "access_start_time_unix_ts": 1687104000.0
            },
            "expected_satellite": "WORLDVIEW3"
        },
        {
            "name": "Unknown satellite (fallback to ISS)",
            "config": {
                "satellite_name": "ISS",
                "satellite_name_key": "satellite_name",
                "tle_file_path": "data/satellites.json"
            },
            "message": {
                "ID": "TEST_006",
                "satellite_name": "UNKNOWN_SATELLITE",
                "aimpoint_latitude": 55.7558,
                "aimpoint_longitude": 37.6176
            },
            "expected_satellite": "UNKNOWN_SATELLITE"
        }
    ]
    
    for i, scenario in enumerate(test_scenarios):
        print(f"\nScenario {i+1}: {scenario['name']}")
        print("-" * 50)
        
        # Create SimPy environment
        env = simpy.Environment()
        env.in_queue = MockQueue()
        env.out_queue = MockQueue()
        
        # Build full configuration
        config = scenario['config'].copy()
        config.update({
            "target_lat_key": "aimpoint_latitude",
            "target_lon_key": "aimpoint_longitude",
            "target_alt_key": "target_alt",
            "start_time_key": "access_start_time_iso",
            "target_lat": 0.0,
            "target_lon": 0.0,
            "target_alt": 0.0,
            "start_time": datetime.now(timezone.utc).isoformat(),
            "duration_seconds": 60,
            "step_seconds": 30,
            "single_time_point": True,
            "storage_key": "geometry_data",
            "time_processing": 0.0,
            "time_delay": 0.0
        })
        
        print(f"Config: satellite_name='{config['satellite_name']}', satellite_name_key='{config['satellite_name_key']}'")
        print(f"Message satellite field: {scenario['message'].get(config['satellite_name_key'], 'Not provided')}")
        print(f"Expected satellite: {scenario['expected_satellite']}")
        
        try:
            # Create CalculateGeometry node
            node = CalculateGeometry(env, f"test_node_{i+1}", config)
            
            # Test satellite lookup directly
            msg = scenario['message']
            satellite_name = msg.get(config['satellite_name_key'], config['satellite_name'])
            tle_line1, tle_line2 = node._get_tle_for_satellite(satellite_name)
            
            if tle_line1 and tle_line2:
                print(f"✓ TLE lookup successful for {satellite_name}")
                print(f"  TLE Line 1: {tle_line1[:30]}...")
                print(f"  TLE Line 2: {tle_line2[:30]}...")
            else:
                print(f"✗ TLE lookup failed for {satellite_name}")
                
        except Exception as e:
            print(f"✗ Error: {e}")

def test_field_mapping_examples():
    """Show examples of different field mapping scenarios"""
    
    print("\n\nField Mapping Examples")
    print("=" * 70)
    
    mapping_examples = [
        {
            "scenario": "Standard TaskAssignment",
            "config": "satellite_name_key: satellite_name",
            "message": '{"satellite_name": "LANDSAT8"}',
            "description": "Uses standard satellite_name field from TaskAssignment"
        },
        {
            "scenario": "Custom Spacecraft Field",
            "config": "satellite_name_key: spacecraft_id",
            "message": '{"spacecraft_id": "TERRA"}',
            "description": "Maps custom spacecraft_id field to satellite name"
        },
        {
            "scenario": "Mission Planning Format",
            "config": "satellite_name_key: vehicle_name",
            "message": '{"vehicle_name": "SENTINEL1A"}',
            "description": "Maps mission planning vehicle_name to satellite"
        },
        {
            "scenario": "Legacy System Format",
            "config": "satellite_name_key: platform_id",
            "message": '{"platform_id": "SPOT7"}',
            "description": "Maps legacy platform_id field to satellite name"
        },
        {
            "scenario": "Multi-Level JSON",
            "config": "satellite_name_key: mission.satellite",
            "message": '{"mission": {"satellite": "HUBBLE"}}',
            "description": "Note: Nested fields not currently supported"
        }
    ]
    
    for example in mapping_examples:
        print(f"\nScenario: {example['scenario']}")
        print(f"  Configuration: {example['config']}")
        print(f"  Message format: {example['message']}")
        print(f"  Description: {example['description']}")

def show_yaml_configurations():
    """Show YAML configuration examples"""
    
    print("\n\nYAML Configuration Examples")
    print("=" * 70)
    
    yaml_examples = [
        {
            "name": "Standard Configuration",
            "yaml": """CalculatePosition:
  type: CalculateGeometry
  satellite_name: ISS                # Default satellite
  satellite_name_key: satellite_name # Standard field name
  tle_file_path: satellites.json
  target_lat_key: aimpoint_latitude
  target_lon_key: aimpoint_longitude"""
        },
        {
            "name": "Custom Field Mapping",
            "yaml": """CalculatePosition:
  type: CalculateGeometry
  satellite_name: TERRA              # Default satellite
  satellite_name_key: spacecraft_id  # Custom field name
  tle_file_path: data/satellites.json
  target_lat_key: aimpoint_latitude
  target_lon_key: aimpoint_longitude"""
        },
        {
            "name": "Mission Planning Format",
            "yaml": """CalculatePosition:
  type: CalculateGeometry
  satellite_name: LANDSAT8
  satellite_name_key: vehicle_name   # Mission planning format
  tle_file_path: /etc/tle/satellites.json
  target_lat_key: observation_lat
  target_lon_key: observation_lon"""
        },
        {
            "name": "Legacy System Integration",
            "yaml": """CalculatePosition:
  type: CalculateGeometry
  satellite_name: HUBBLE
  satellite_name_key: platform_id    # Legacy system format
  tle_file_path: legacy_tle.json
  target_lat_key: target_latitude
  target_lon_key: target_longitude"""
        }
    ]
    
    for example in yaml_examples:
        print(f"\n{example['name']}:")
        print(example['yaml'])

def show_message_examples():
    """Show message format examples"""
    
    print("\n\nMessage Format Examples")
    print("=" * 70)
    
    message_examples = [
        {
            "name": "TaskAssignment Message",
            "config_key": "satellite_name",
            "message": """{
  "assignment_id": "12345-abcde",
  "satellite_name": "LANDSAT8",
  "target_id": "target_001",
  "aimpoint_latitude": 40.7128,
  "aimpoint_longitude": -74.0060,
  "access_start_time_unix_ts": 1687104000.0
}"""
        },
        {
            "name": "Custom Spacecraft Message", 
            "config_key": "spacecraft_id",
            "message": """{
  "mission_id": "EO-2025-001",
  "spacecraft_id": "TERRA",
  "observation_lat": 35.6762,
  "observation_lon": 139.6503,
  "observation_time": "2025-06-15T12:00:00Z"
}"""
        },
        {
            "name": "Legacy Platform Message",
            "config_key": "platform_id", 
            "message": """{
  "request_id": "REQ-98765",
  "platform_id": "SPOT7",
  "target_coordinates": {
    "latitude": 51.5074,
    "longitude": -0.1278
  }
}"""
        }
    ]
    
    for example in message_examples:
        print(f"\n{example['name']} (satellite_name_key: {example['config_key']}):")
        print(example['message'])

if __name__ == "__main__":
    try:
        test_satellite_name_key_scenarios()
        test_field_mapping_examples()
        show_yaml_configurations()
        show_message_examples()
        
        print("\n🎯 SUMMARY")
        print("=" * 70)
        print("satellite_name_key configuration enables:")
        print("• Flexible satellite name field mapping")
        print("• Support for different message schemas")
        print("• Integration with legacy systems")
        print("• Custom field naming conventions")
        print("• Runtime satellite selection via any field name")
        print("• Backwards compatibility with existing systems")
        
    except KeyboardInterrupt:
        print("\nTest interrupted by user")
    except Exception as e:
        print(f"Test failed with error: {e}")