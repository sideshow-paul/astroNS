import sys
import os
import simpy
from datetime import datetime

# Add source directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'astroNS'))

# Import the CalculateGSD node
from nodes.aerospace.calculate_gsd import CalculateGSD

class MockQueue:
    def __init__(self):
        self.items = []
    
    def get(self):
        if self.items:
            return self.items.pop(0)
        return None
    
    def put(self, item):
        self.items.append(item)

def test_calculate_gsd_node():
    """Test the CalculateGSD node with different scenarios"""
    
    # Create SimPy environment
    env = simpy.Environment()
    env.in_queue = MockQueue()
    env.out_queue = MockQueue()
    
    # Configuration parameters
    config = {
        # Default sensor parameters for a typical satellite camera
        "sensor_height_mm": 36.0,   # Full-frame sensor height
        "sensor_width_mm": 24.0,    # Full-frame sensor width
        "focal_length_mm": 500.0,   # Long focal length for satellite imaging
        "image_height_px": 6000,    # High resolution image height
        "image_width_px": 4000,     # High resolution image width
        "use_sensor_height": True,  # Use sensor height for calculation
        "gsd_storage_key": "gsd_result",  # Key to store the GSD result
        "use_ecef_positions": False,  # Default to using direct distance values
        "geometry_results_key": "geometry_results",  # Key for geometry data
    }
    
    # Create CalculateGSD node
    gsd_calculator = CalculateGSD(
        env=env,
        name="test_gsd_calculator",
        configuration=config
    )
    
    # Define a process to send test input messages
    def input_process():
        # Wait a bit to let the node initialize
        yield env.timeout(1)
        
        # Test Case 1: Low Earth Orbit satellite (~400km)
        leo_input = {
            "ID": "LEO_Satellite",
            "distance_km": 400.0,  # 400 km distance
            "sensor_type": "high_resolution"
        }
        env.in_queue.put(leo_input)
        
        # Wait a bit between inputs
        yield env.timeout(5)
        
        # Test Case 2: Medium Earth Orbit satellite (~20,000km)
        meo_input = {
            "ID": "MEO_Satellite",
            "distance_km": 20000.0,  # 20,000 km distance
            "sensor_type": "medium_resolution",
            "focal_length_mm": 300.0  # Different focal length
        }
        env.in_queue.put(meo_input)
        
        # Wait a bit between inputs
        yield env.timeout(5)
        
        # Test Case 3: Drone at low altitude
        drone_input = {
            "ID": "Drone",
            "distance_km": 0.15,  # 150 m = 0.15 km distance
            "sensor_width_mm": 13.2,  # Different sensor size
            "sensor_height_mm": 8.8,  # Different sensor size
            "focal_length_mm": 35.0,  # Different focal length
            "image_width_px": 3840,  # 4K resolution width
            "image_height_px": 2160,  # 4K resolution height
            "use_sensor_height": False  # Use width instead of height
        }
        env.in_queue.put(drone_input)
        
        # Wait a bit between inputs
        yield env.timeout(5)
        
        # Test Case 4: Using ECEF positions to calculate distance
        ecef_input = {
            "ID": "ECEF_Distance_Test",
            # Source position (satellite) in ECEF (km)
            "source_pos_ecef_km": [6778.0, 0.0, 0.0],  # Example: satellite at 400km above Earth radius
            # Target position (ground point) in ECEF (km)
            "target_pos_ecef_km": [6378.0, 0.0, 0.0],  # Example: point on Earth surface
            "focal_length_mm": 600.0  # Different focal length
        }
        
        # Create a new config with ECEF calculation enabled
        ecef_config = config.copy()
        ecef_config["use_ecef_positions"] = True
        
        # Update the node configuration
        gsd_calculator.configuration = ecef_config
        
        # Send the input
        env.in_queue.put(ecef_input)
        
        # Wait a bit between inputs
        yield env.timeout(5)
        
        # Test Case 5: Using geometry_results data (simulating CalculateGeometry node output)
        geometry_input = {
            "ID": "Geometry_Results_Test",
            "geometry_results": [
                {
                    "time": "2023-06-15T12:00:00Z",
                    "grazing_angle_deg": 25.5,
                    "distance_km": 420.8,
                    "azimuth_deg": 45.2,
                    "elevation_deg": 30.1,
                    "sun_elevation_deg": -15.3,
                    "observer_position_ecef_km": [6798.0, 100.0, 50.0],
                    "target_position_ecef_km": [6378.0, 0.0, 0.0],
                    "is_visible": True,
                    "is_day": False,
                    "is_in_eclipse": True
                },
                {
                    "time": "2023-06-15T12:01:00Z",
                    "grazing_angle_deg": 26.1,
                    "distance_km": 425.3,
                    "azimuth_deg": 46.0,
                    "elevation_deg": 29.8,
                    "sun_elevation_deg": -15.1,
                    "observer_position_ecef_km": [6800.0, 110.0, 52.0],
                    "target_position_ecef_km": [6378.0, 0.0, 0.0],
                    "is_visible": True,
                    "is_day": False,
                    "is_in_eclipse": True
                }
            ],
            "focal_length_mm": 450.0  # Different focal length
        }
        
        env.in_queue.put(geometry_input)
    
    # Define a process to read output from the node
    def output_process():
        while True:
            # Wait until we have output data
            yield env.timeout(2)
            
            # Check if there are results
            if env.out_queue.items:
                output_data = env.out_queue.items.pop(0)
                
                # Print the results
                gsd_key = config["gsd_storage_key"]
                gsd_value = output_data.get(gsd_key, 0.0)
                
                print(f"ID: {output_data.get('ID', 'unknown')}")
                print(f"Distance: {output_data.get('distance_km', 0.0):.3f} kilometers")
                
                # Print ECEF positions if available
                if "source_pos_ecef_km" in output_data and "target_pos_ecef_km" in output_data:
                    print(f"Source ECEF: {output_data['source_pos_ecef_km']}")
                    print(f"Target ECEF: {output_data['target_pos_ecef_km']}")
                
                # Print geometry results if available
                if "geometry_results" in output_data:
                    geometry_results = output_data["geometry_results"]
                    if geometry_results and len(geometry_results) > 0:
                        print(f"Using geometry data from {len(geometry_results)} time points")
                        print(f"First geometry point - Distance: {geometry_results[0].get('distance_km', 'N/A'):.3f} km")
                        print(f"First geometry point - Elevation: {geometry_results[0].get('elevation_deg', 'N/A'):.2f}°")
                
                print(f"GSD: {gsd_value:.6f} meters/pixel")
                
                # Calculate additional derived metrics
                if gsd_value > 0:
                    # Area covered by a single pixel in square meters
                    pixel_area = gsd_value * gsd_value
                    print(f"Area per pixel: {pixel_area:.6f} m²")
                    
                    # Width of the entire image footprint
                    if "image_width_px" in output_data:
                        image_width_px = output_data["image_width_px"]
                        footprint_width = gsd_value * image_width_px
                        print(f"Image footprint width: {footprint_width:.2f} meters")
                    
                    # Height of the entire image footprint
                    if "image_height_px" in output_data:
                        image_height_px = output_data["image_height_px"]
                        footprint_height = gsd_value * image_height_px
                        print(f"Image footprint height: {footprint_height:.2f} meters")
                
                print("----------------------------")
    
    # Add processes to the environment
    env.process(input_process())
    env.process(output_process())
    
    # Run the simulation
    env.run(until=20)

if __name__ == "__main__":
    test_calculate_gsd_node()