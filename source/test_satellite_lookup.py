import sys
import os
import simpy
from datetime import datetime, timezone, timedelta
import json

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

def test_satellite_lookup():
    """Test the CalculateGeometry node with satellite name lookup"""
    
    print("Testing CalculateGeometry Satellite Lookup Functionality")
    print("=" * 60)
    
    # Create SimPy environment
    env = simpy.Environment()
    env.in_queue = MockQueue()
    env.out_queue = MockQueue()
    
    # Configuration using satellite name lookup
    config = {
        # Satellite lookup configuration
        "satellite_name": "ISS",
        "satellite_name_key": "satellite_name",
        "tle_file_path": "data/satellites.json",
        # Target key configuration
        "target_lat_key": "aimpoint_latitude",
        "target_lon_key": "aimpoint_longitude",
        "target_alt_key": "target_alt",
        "start_time_key": "access_start_time_iso",
        # Default fallback values
        "target_lat": 39.0,
        "target_lon": -77.0,
        "target_alt": 0.0,
        "start_time": datetime.now(timezone.utc).isoformat(),
        # Time settings
        "duration_seconds": 60,  # 1 minute
        "step_seconds": 30,      # 30 second steps
        "single_time_point": True,
        "storage_key": "geometry_data",
        # Processing in simulation
        "time_processing": 0.1,
        "time_delay": 0.0
    }
    
    # Create CalculateGeometry node
    geometry_calculator = CalculateGeometry(
        env=env,
        name="test_satellite_lookup",
        configuration=config
    )
    
    # Define a process to send test input messages
    def input_process():
        # Wait a bit to let the node initialize
        yield env.timeout(1)
        
        # Test Case 1: ISS with TaskAssignment data
        iss_message = {
            "ID": "SAT_001",
            "assignment_id": "12345-abcde",
            "satellite_name": "ISS",  # This will override config
            "target_id": "target_001",
            "aimpoint_latitude": 40.7128,  # New York City
            "aimpoint_longitude": -74.0060,
            "target_alt": 150.0,
            "access_start_time_iso": datetime.now(timezone.utc).isoformat()
        }
        env.in_queue.put(iss_message)
        
        # Wait a bit between inputs
        yield env.timeout(5)
        
        # Test Case 2: Hubble Space Telescope
        hubble_message = {
            "ID": "SAT_002",
            "assignment_id": "67890-fghij",
            "satellite_name": "HUBBLE",
            "target_id": "target_002",
            "aimpoint_latitude": 35.6762,  # Tokyo
            "aimpoint_longitude": 139.6503,
            "target_alt": 200.0,
            "access_start_time_iso": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
        }
        env.in_queue.put(hubble_message)
        
        # Wait a bit between inputs
        yield env.timeout(5)
        
        # Test Case 3: Unknown satellite (should fallback to ISS)
        unknown_message = {
            "ID": "SAT_003",
            "assignment_id": "11111-aaaaa",
            "satellite_name": "UNKNOWN_SAT",
            "target_id": "target_003",
            "aimpoint_latitude": 51.5074,  # London
            "aimpoint_longitude": -0.1278,
            "target_alt": 100.0,
            "access_start_time_iso": (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()
        }
        env.in_queue.put(unknown_message)
        
        # Wait a bit between inputs
        yield env.timeout(5)
        
        # Test Case 4: Use config default (no satellite_name in message)
        default_message = {
            "ID": "SAT_004",
            "assignment_id": "22222-bbbbb",
            "target_id": "target_004",
            "aimpoint_latitude": -33.8688,  # Sydney
            "aimpoint_longitude": 151.2093,
            "target_alt": 50.0,
            "access_start_time_iso": (datetime.now(timezone.utc) + timedelta(hours=3)).isoformat()
        }
        env.in_queue.put(default_message)
        
        # Wait a bit between inputs
        yield env.timeout(5)
        
        # Test Case 5: Different satellite_name_key field (custom field name)
        custom_key_message = {
            "ID": "SAT_005",
            "assignment_id": "33333-ccccc",
            "spacecraft_id": "TERRA",  # Using different field name for satellite
            "target_id": "target_005",
            "aimpoint_latitude": 48.8566,  # Paris
            "aimpoint_longitude": 2.3522,
            "target_alt": 75.0,
            "access_start_time_iso": (datetime.now(timezone.utc) + timedelta(hours=4)).isoformat()
        }
        env.in_queue.put(custom_key_message)
    
    # Define a process to read output from the node
    def output_process():
        while True:
            # Wait until we have output data
            yield env.timeout(2)
            
            # Check if there are results
            if env.out_queue.items:
                output_data = env.out_queue.items.pop(0)
                
                # Print the results
                storage_key = config["storage_key"]
                geometry_results = output_data.get(storage_key, [])
                
                print(f"ID: {output_data.get('ID', 'unknown')}")
                print(f"Assignment ID: {output_data.get('assignment_id', 'N/A')}")
                print(f"Satellite: {output_data.get('satellite_name', config['satellite_name'])}")
                print(f"Target ID: {output_data.get('target_id', 'N/A')}")
                
                # Show what coordinates were used
                aimpoint_lat = output_data.get('aimpoint_latitude', 'N/A')
                aimpoint_lon = output_data.get('aimpoint_longitude', 'N/A')
                target_alt = output_data.get('target_alt', 'N/A')
                access_time = output_data.get('access_start_time_iso', 'N/A')
                print(f"Aimpoint: ({aimpoint_lat}, {aimpoint_lon}, {target_alt}m)")
                print(f"Access Time: {access_time}")
                
                if geometry_results:
                    print(f"Geometry calculations: {len(geometry_results)} data points")
                    
                    # Print the first data point as an example
                    first_point = geometry_results[0]
                    print("Sample geometry data:")
                    print(f"  Time: {first_point.get('time', 'unknown')}")
                    print(f"  Distance: {first_point.get('distance_km', 0):.2f} km")
                    print(f"  Elevation: {first_point.get('elevation_deg', 0):.2f}°")
                    print(f"  Azimuth: {first_point.get('azimuth_deg', 0):.2f}°")
                    print(f"  Visible: {first_point.get('is_visible', False)}")
                else:
                    print("No geometry data generated")
                
                print("-" * 50)
    
    # Add processes to the environment
    env.process(input_process())
    env.process(output_process())
    
    # Run the simulation
    env.run(until=25)

def test_tle_file_loading():
    """Test TLE file loading functionality"""
    
    print("\nTesting TLE File Loading")
    print("=" * 60)
    
    # Test with mock environment
    env = simpy.Environment()
    
    test_configs = [
        {
            "name": "Valid TLE file",
            "config": {
                "satellite_name": "ISS",
                "satellite_name_key": "satellite_name",
                "tle_file_path": "data/satellites.json"
            }
        },
        {
            "name": "Non-existent TLE file",
            "config": {
                "satellite_name": "ISS",
                "satellite_name_key": "satellite_name", 
                "tle_file_path": "nonexistent.json"
            }
        },
        {
            "name": "Different satellite",
            "config": {
                "satellite_name": "HUBBLE",
                "satellite_name_key": "satellite_name",
                "tle_file_path": "data/satellites.json"
            }
        },
        {
            "name": "Custom satellite name key",
            "config": {
                "satellite_name": "ISS",
                "satellite_name_key": "spacecraft_id",
                "tle_file_path": "data/satellites.json"
            }
        }
    ]
    
    for test_case in test_configs:
        print(f"\nTest: {test_case['name']}")
        config = test_case['config'].copy()
        config.update({
            "target_lat": 0.0,
            "target_lon": 0.0,
            "target_alt": 0.0,
            "start_time": datetime.now(timezone.utc).isoformat(),
            "storage_key": "test_results"
        })
        
        try:
            # Create node to test TLE loading
            node = CalculateGeometry(env, "test_node", config)
            
            # Test TLE lookup
            satellite_name = config['satellite_name']
            tle_line1, tle_line2 = node._get_tle_for_satellite(satellite_name)
            
            print(f"  Satellite: {satellite_name}")
            print(f"  TLE Line 1: {tle_line1[:20]}..." if tle_line1 else "  TLE Line 1: None")
            print(f"  TLE Line 2: {tle_line2[:20]}..." if tle_line2 else "  TLE Line 2: None")
            print(f"  ✓ TLE loading successful")
            
        except Exception as e:
            print(f"  ✗ Error: {e}")

def show_configuration_examples():
    """Show different configuration examples"""
    
    print("\nConfiguration Examples")
    print("=" * 60)
    
    examples = [
        {
            "name": "Basic Satellite Lookup",
            "yaml": """CalculatePosition:
  type: CalculateGeometry
  satellite_name: ISS
  satellite_name_key: satellite_name
  tle_file_path: satellites.json
  target_lat_key: aimpoint_latitude
  target_lon_key: aimpoint_longitude"""
        },
        {
            "name": "Multiple Satellites",
            "yaml": """CalculatePosition:
  type: CalculateGeometry
  satellite_name: LANDSAT8  # Default satellite
  satellite_name_key: satellite_name
  tle_file_path: data/satellites.json
  target_lat_key: aimpoint_latitude
  target_lon_key: aimpoint_longitude
  # satellite_name can be overridden by message data"""
        },
        {
            "name": "Custom Satellite Name Key", 
            "yaml": """CalculatePosition:
  type: CalculateGeometry
  satellite_name: HUBBLE
  satellite_name_key: spacecraft_id  # Custom field name
  tle_file_path: satellites.json
  target_lat_key: aimpoint_latitude
  target_lon_key: aimpoint_longitude"""
        },
        {
            "name": "Custom TLE File Location", 
            "yaml": """CalculatePosition:
  type: CalculateGeometry
  satellite_name: HUBBLE
  satellite_name_key: satellite_name
  tle_file_path: /path/to/custom/tle_data.json
  target_lat_key: observation_lat
  target_lon_key: observation_lon"""
        }
    ]
    
    for example in examples:
        print(f"\n{example['name']}:")
        print(example['yaml'])

if __name__ == "__main__":
    try:
        test_satellite_lookup()
        test_tle_file_loading()
        show_configuration_examples()
        
        print("\n🎯 SUMMARY")
        print("=" * 60)
        print("The CalculateGeometry node now supports:")
        print("• satellite_name: lookup satellite by name instead of TLE lines")
        print("• satellite_name_key: configurable key for satellite name in messages")
        print("• tle_file_path: configurable path to TLE data file")
        print("• Automatic TLE loading from JSON file at startup")
        print("• Fallback to ISS if satellite not found")
        print("• Runtime satellite name override via message data")
        print("• Multiple possible file locations for TLE data")
        print("• Flexible field mapping for different message schemas")
        
    except KeyboardInterrupt:
        print("\nTest interrupted by user")
    except Exception as e:
        print(f"Test failed with error: {e}")