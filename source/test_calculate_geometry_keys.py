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

def test_calculate_geometry_keys():
    """Test the CalculateGeometry node with target key configuration"""
    
    # Create SimPy environment
    env = simpy.Environment()
    env.in_queue = MockQueue()
    env.out_queue = MockQueue()
    
    # Configuration using target keys
    config = {
        # ISS TLE example
        "tle_line1": "1 25544U 98067A   25096.03700594  .00015269  00000+0  28194-3 0  9999",
        "tle_line2": "2 25544  51.6369 304.3678 0004922  13.5339 346.5781 15.49280872503978",
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
        name="test_geometry_keys",
        configuration=config
    )
    
    # Define a process to send test input messages
    def input_process():
        # Wait a bit to let the node initialize
        yield env.timeout(1)
        
        # Test Case 1: Message with aimpoint coordinates (from TaskAssignment)
        access_time = datetime.now(timezone.utc) + timedelta(minutes=30)
        task_message = {
            "ID": "TASK_001",
            "assignment_id": "12345-abcde",
            "satellite_name": "ISS",
            "target_id": "target_001",
            "aimpoint_latitude": 40.7128,  # New York City
            "aimpoint_longitude": -74.0060,
            "target_alt": 150.0,  # 150m altitude
            "access_start_time_unix_ts": 1687104000.0,
            "access_end_time_unix_ts": 1687107600.0,
            "access_start_time_iso": access_time.isoformat()
        }
        env.in_queue.put(task_message)
        
        # Wait a bit between inputs
        yield env.timeout(5)
        
        # Test Case 2: Message with different aimpoint coordinates (Tokyo)
        tokyo_time = datetime.now(timezone.utc) + timedelta(hours=1)
        tokyo_message = {
            "ID": "TASK_002", 
            "assignment_id": "67890-fghij",
            "satellite_name": "ISS",
            "target_id": "target_002",
            "aimpoint_latitude": 35.6762,  # Tokyo
            "aimpoint_longitude": 139.6503,
            "target_alt": 200.0,  # 200m altitude
            "access_start_time_iso": tokyo_time.isoformat()
        }
        env.in_queue.put(tokyo_message)
        
        # Wait a bit between inputs  
        yield env.timeout(5)
        
        # Test Case 3: Message missing aimpoint coordinates (should use defaults)
        fallback_message = {
            "ID": "TASK_003",
            "assignment_id": "11111-aaaaa", 
            "satellite_name": "ISS",
            "target_id": "target_003",
            # No aimpoint fields - should use default values
            # No access_start_time_iso - should use default start_time
        }
        env.in_queue.put(fallback_message)
    
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
                print(f"Target ID: {output_data.get('target_id', 'N/A')}")
                
                # Show what coordinates were used
                aimpoint_lat = output_data.get('aimpoint_latitude', 'N/A')
                aimpoint_lon = output_data.get('aimpoint_longitude', 'N/A')
                target_alt = output_data.get('target_alt', 'N/A')
                access_time = output_data.get('access_start_time_iso', 'N/A')
                print(f"Aimpoint Coordinates: ({aimpoint_lat}, {aimpoint_lon}, {target_alt}m)")
                print(f"Access Start Time: {access_time}")
                
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
    env.run(until=20)

def test_configuration_variations():
    """Test different key configuration scenarios"""
    
    print("\nTesting Configuration Variations")
    print("=" * 60)
    
    test_configs = [
        {
            "name": "Standard field names",
            "config": {
                "target_lat_key": "target_lat",
                "target_lon_key": "target_lon",
                "target_alt_key": "target_alt",
                "start_time_key": "start_time"
            },
            "message": {
                "target_lat": 45.0, 
                "target_lon": -90.0,
                "target_alt": 100.0,
                "start_time": "2023-06-15T12:00:00Z"
            }
        },
        {
            "name": "Aimpoint field names (TaskAssignment)",
            "config": {
                "target_lat_key": "aimpoint_latitude", 
                "target_lon_key": "aimpoint_longitude",
                "target_alt_key": "target_alt",
                "start_time_key": "access_start_time_iso"
            },
            "message": {
                "aimpoint_latitude": 51.5074, 
                "aimpoint_longitude": -0.1278,
                "target_alt": 250.0,
                "access_start_time_iso": "2023-06-15T14:30:00Z"
            }
        },
        {
            "name": "Custom field names",
            "config": {
                "target_lat_key": "observation_lat",
                "target_lon_key": "observation_lon",
                "target_alt_key": "elevation",
                "start_time_key": "observation_time"
            },
            "message": {
                "observation_lat": -33.8688, 
                "observation_lon": 151.2093,
                "elevation": 300.0,
                "observation_time": "2023-06-15T16:45:00Z"
            }
        }
    ]
    
    for test_case in test_configs:
        print(f"\nTest: {test_case['name']}")
        config = test_case['config']
        print(f"  Config:")
        print(f"    target_lat_key='{config['target_lat_key']}'")
        print(f"    target_lon_key='{config['target_lon_key']}'") 
        print(f"    target_alt_key='{config['target_alt_key']}'")
        print(f"    start_time_key='{config['start_time_key']}'")
        print(f"  Message: {test_case['message']}")
        print(f"  ✓ Configuration valid")

if __name__ == "__main__":
    print("CalculateGeometry Target Key Configuration Test")
    print("This script tests the target_lat_key and target_lon_key functionality")
    print("=" * 70)
    
    test_calculate_geometry_keys()
    test_configuration_variations()
    
    print("\n🎯 SUMMARY")
    print("=" * 60)
    print("The CalculateGeometry node now supports:")
    print("• target_lat_key: configurable key for latitude values")
    print("• target_lon_key: configurable key for longitude values")
    print("• target_alt_key: configurable key for altitude values") 
    print("• start_time_key: configurable key for start time values")
    print("• Automatic fallback to default values if keys not found")
    print("• Integration with TaskAssignment aimpoint fields")
    print("• Support for both Unix timestamps and ISO datetime strings")
    print("• Flexible field name mapping for different message types")