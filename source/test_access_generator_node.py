import sys
import os
import json
from datetime import datetime, timezone, timedelta
import simpy

# Add source directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'astroNS'))

# Import the AccessGenerator node
from nodes.aerospace.accessGenerator import AccessGenerator

class MockQueue:
    def __init__(self):
        self.items = []
    
    def get(self):
        if self.items:
            return self.items.pop(0)
        return None
    
    def put(self, item):
        self.items.append(item)

def test_access_generator_node():
    # Create SimPy environment
    env = simpy.Environment()
    env.in_queue = MockQueue()
    env.out_queue = MockQueue()
    
    # Configuration parameters
    config = {
        # ISS TLE (example)
        'tle_line1': "1 25544U 98067A   25124.47945869  .00007832  00000-0  14843-3 0  9999",
        'tle_line2': "2 25544  51.6347 163.5573 0002292  78.0470 282.0775 15.49336034508382",
        # Ashburn, VA
        'target_lat': 39.0438,
        'target_lon': -77.4874,
        'target_alt': 0.0,
        # Analysis parameters
        'start_time': datetime.now(timezone.utc).isoformat(),
        'duration_seconds': 86400,  # 1 day
        'step_seconds': 60,  # 1 minute steps
        # Constraint parameters
        'min_grazing_angle': 10.0,
        'sun_min_angle': -90.0,
        'sun_max_angle': 0.0,
        # Storage key for results
        'storage_key': 'Access_Results'
    }
    
    # Create AccessGenerator node
    access_gen = AccessGenerator(
        env=env,
        name="test_access_generator",
        configuration=config
    )
    
    # Define a process to send input to the node
    def input_process():
        # Wait a bit to let the node initialize
        yield env.timeout(1)
        
        # Send input data
        input_data = {
            'ID': '12345',
            'satellite_id': 'ISS',
            'target_id': 'Ashburn',
            # Override with a shorter duration for testing
            'duration_seconds': 43200  # 12 hours
        }
        
        env.in_queue.put(input_data)
    
    # Define a process to read output from the node
    def output_process():
        # Wait for processing to complete
        yield env.timeout(10)
        
        # Get output data from queue
        if env.out_queue.items:
            output_data = env.out_queue.items[0]
            
            # Print the results
            print(f"Satellite: {output_data.get('satellite_id', 'unknown')}")
            print(f"Target: {output_data.get('target_id', 'unknown')}")
            
            # Print each access period
            storage_key = config['storage_key']
            accesses = output_data.get(storage_key, [])
            print(f"Total accesses: {len(accesses)}")
            
            for access in accesses:
                print(f"Access {access['access_id']}:")
                print(f"  Start: {access['start_time']}")
                print(f"  End: {access['end_time']}")
                print(f"  Duration: {access['duration_seconds']} seconds")
                print(f"  Grazing angle (min/max/avg): {access['grazing_angle']['min']:.2f}°/{access['grazing_angle']['max']:.2f}°/{access['grazing_angle']['avg']:.2f}°")
                print(f"  Sun elevation (min/max/avg): {access['sun_elevation']['min']:.2f}°/{access['sun_elevation']['max']:.2f}°/{access['sun_elevation']['avg']:.2f}°")
                print()
            
            # Save to JSON file
            with open('access_results.json', 'w') as f:
                json.dump(output_data, f, indent=2)
                
            print(f"Results saved to access_results.json")
    
    # Add processes to the environment
    env.process(input_process())
    env.process(output_process())
    
    # Run the simulation
    env.run(until=100)

if __name__ == "__main__":
    test_access_generator_node()