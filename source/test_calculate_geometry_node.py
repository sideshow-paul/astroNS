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

def test_calculate_geometry_node():
    """Test the CalculateGeometry node with different scenarios"""
    
    # Create SimPy environment
    env = simpy.Environment()
    env.in_queue = MockQueue()
    env.out_queue = MockQueue()
    
    # Configuration parameters
    config = {
        # ISS TLE example
        "tle_line1": "1 25544U 98067A   25096.03700594  .00015269  00000+0  28194-3 0  9999",
        "tle_line2": "2 25544  51.6369 304.3678 0004922  13.5339 346.5781 15.49280872503978",
        # Example target location (Washington DC)
        "target_lat": 38.9072,
        "target_lon": -77.0369,
        "target_alt": 0.0,
        # Time settings
        "start_time": datetime.now(timezone.utc).isoformat(),
        "duration_seconds": 7200,  # 2 hours
        "step_seconds": 300,       # 5 minute steps
        "storage_key": "geometry_data",
        # Processing in simulation
        "time_processing": 0.1,
        "time_delay": 0.0
    }
    
    # Create CalculateGeometry node
    geometry_calculator = CalculateGeometry(
        env=env,
        name="test_geometry_calculator",
        configuration=config
    )
    
    # Define a process to send test input messages
    def input_process():
        # Wait a bit to let the node initialize
        yield env.timeout(1)
        
        # Test Case 1: Standard calculation with ISS
        standard_input = {
            "ID": "ISS_Geometry_Standard",
            "start_time": datetime.now(timezone.utc).isoformat()
        }
        env.in_queue.put(standard_input)
        
        # Wait a bit between inputs
        yield env.timeout(5)
        
        # Test Case 2: Single time point calculation
        single_time_input = {
            "ID": "ISS_Geometry_SingleTime",
            "single_time_point": True,
            "start_time": (datetime.now(timezone.utc) + timedelta(hours=3)).isoformat()
        }
        env.in_queue.put(single_time_input)
        
        # Wait a bit between inputs
        yield env.timeout(5)
        
        # Test Case 3: Different target location (Tokyo)
        tokyo_input = {
            "ID": "ISS_Geometry_Tokyo",
            "target_lat": 35.6762,
            "target_lon": 139.6503,
            "duration_seconds": 3600  # 1 hour
        }
        env.in_queue.put(tokyo_input)
    
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
                print(f"Number of geometry data points: {len(geometry_results)}")
                
                if geometry_results:
                    # Print the first data point as an example
                    first_point = geometry_results[0]
                    print("\nSample data point:")
                    print(f"  Time: {first_point.get('time', 'unknown')}")
                    print(f"  Grazing angle: {first_point.get('grazing_angle_deg', 0):.2f}°")
                    print(f"  Distance: {first_point.get('distance_km', 0):.2f} km")
                    print(f"  Azimuth: {first_point.get('azimuth_deg', 0):.2f}°")
                    print(f"  Elevation: {first_point.get('elevation_deg', 0):.2f}°")
                    print(f"  Sun elevation: {first_point.get('sun_elevation_deg', 0):.2f}°")
                    print(f"  Visible: {first_point.get('is_visible', False)}")
                    print(f"  Daytime: {first_point.get('is_day', False)}")
                    print(f"  In eclipse: {first_point.get('is_in_eclipse', False)}")
                    
                    # Save to JSON file
                    filename = f"geometry_results_{output_data.get('ID', 'unknown')}.json"
                    with open(filename, 'w') as f:
                        json.dump(output_data, f, indent=2)
                    print(f"\nResults saved to {filename}")
                
                print("-" * 50)
    
    # Add processes to the environment
    env.process(input_process())
    env.process(output_process())
    
    # Run the simulation
    env.run(until=20)

if __name__ == "__main__":
    test_calculate_geometry_node()