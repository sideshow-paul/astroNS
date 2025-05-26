import sys
import os
import simpy
from datetime import datetime, timezone, timedelta

# Add source directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'astroNS'))

# Import the KeyDelayTime node
from nodes.core.network.keydelaytime import KeyDelayTime

class MockQueue:
    def __init__(self):
        self.items = []
    
    def get(self):
        if self.items:
            return self.items.pop(0)
        return None
    
    def put(self, item):
        self.items.append(item)

def test_keydelaytime_unix_conversion():
    """Test the KeyDelayTime node with Unix time conversion"""
    
    # Create SimPy environment with epoch
    env = simpy.Environment()
    env.in_queue = MockQueue()
    env.out_queue = MockQueue()
    
    # Set simulation epoch to a known time
    env.epoch = datetime(2023, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
    
    # Configuration with Unix time conversion enabled
    config_unix = {
        "delay_key": "target_time_unix",
        "convert_unix_time": True
    }
    
    # Configuration without Unix time conversion (standard mode)
    config_standard = {
        "delay_key": "target_time_sim",
        "convert_unix_time": False
    }
    
    # Configuration with ISO datetime conversion enabled
    config_iso = {
        "delay_key": "target_time_iso",
        "convert_iso_datetime": True
    }
    
    # Create KeyDelayTime nodes
    delay_node_unix = KeyDelayTime(
        env=env,
        name="test_unix_delay",
        configuration=config_unix
    )
    
    delay_node_standard = KeyDelayTime(
        env=env,
        name="test_standard_delay", 
        configuration=config_standard
    )
    
    delay_node_iso = KeyDelayTime(
        env=env,
        name="test_iso_delay",
        configuration=config_iso
    )
    
    # Define a process to send test input messages
    def input_process():
        # Wait a bit to let nodes initialize
        yield env.timeout(1)
        
        # Test Case 1: Unix time conversion - future time
        future_unix_time = env.epoch.timestamp() + 3600  # 1 hour after epoch
        unix_input = {
            "ID": "UNIX_TEST_001",
            "target_time_unix": future_unix_time,
            "message": "Test Unix time conversion"
        }
        env.in_queue.put(unix_input)
        
        # Wait and process
        yield env.timeout(10)
        
        # Test Case 2: Unix time conversion - past time (should warn)
        past_unix_time = env.epoch.timestamp() - 1800  # 30 minutes before epoch
        past_unix_input = {
            "ID": "UNIX_TEST_002", 
            "target_time_unix": past_unix_time,
            "message": "Test past Unix time (should warn)"
        }
        env.in_queue.put(past_unix_input)
        
        # Wait and process
        yield env.timeout(10)
        
        # Test Case 3: Standard mode - simulation time
        sim_time_input = {
            "ID": "SIM_TEST_001",
            "target_time_sim": env.now + 1800,  # 30 minutes from now in sim time
            "message": "Test standard simulation time"
        }
        env.in_queue.put(sim_time_input)
        
        # Wait and process
        yield env.timeout(10)
        
        # Test Case 4: Unix time conversion - current time
        current_unix_time = env.epoch.timestamp() + env.now
        current_input = {
            "ID": "UNIX_TEST_003",
            "target_time_unix": current_unix_time,
            "message": "Test current Unix time"
        }
        env.in_queue.put(current_input)
        
        # Wait and process
        yield env.timeout(10)
        
        # Test Case 5: ISO datetime conversion - future time
        future_iso_time = (env.epoch + timedelta(hours=2)).isoformat()
        iso_input = {
            "ID": "ISO_TEST_001",
            "target_time_iso": future_iso_time,
            "message": "Test ISO datetime conversion"
        }
        env.in_queue.put(iso_input)
        
        # Wait and process
        yield env.timeout(10)
        
        # Test Case 6: ISO datetime conversion - past time (should warn)
        past_iso_time = (env.epoch - timedelta(minutes=45)).isoformat()
        past_iso_input = {
            "ID": "ISO_TEST_002",
            "target_time_iso": past_iso_time,
            "message": "Test past ISO datetime (should warn)"
        }
        env.in_queue.put(past_iso_input)
        
        # Wait and process
        yield env.timeout(10)
        
        # Test Case 7: ISO datetime with Z suffix
        z_suffix_time = (env.epoch + timedelta(minutes=90)).isoformat() + "Z"
        z_suffix_input = {
            "ID": "ISO_TEST_003",
            "target_time_iso": z_suffix_time,
            "message": "Test ISO datetime with Z suffix"
        }
        env.in_queue.put(z_suffix_input)
        
        # Wait and process
        yield env.timeout(10)
        
        # Test Case 8: Error handling - invalid Unix time
        invalid_input = {
            "ID": "ERROR_TEST_001",
            "target_time_unix": "invalid_time",
            "message": "Test error handling"
        }
        env.in_queue.put(invalid_input)
        
        # Wait and process
        yield env.timeout(10)
        
        # Test Case 9: Error handling - invalid ISO datetime
        invalid_iso_input = {
            "ID": "ERROR_TEST_002",
            "target_time_iso": "invalid_datetime_string",
            "message": "Test ISO datetime error handling"
        }
        env.in_queue.put(invalid_iso_input)
    
    # Define a process to read output from nodes
    def output_process():
        while True:
            # Wait until we have output data
            yield env.timeout(5)
            
            # Check if there are results
            while env.out_queue.items:
                output_data = env.out_queue.items.pop(0)
                
                print(f"Output received at sim time {env.now:.2f}:")
                print(f"  ID: {output_data.get('ID', 'unknown')}")
                print(f"  Message: {output_data.get('message', 'No message')}")
                
                # Show timing information
                if 'target_time_unix' in output_data:
                    unix_time = output_data['target_time_unix']
                    unix_datetime = datetime.fromtimestamp(unix_time, tz=timezone.utc)
                    print(f"  Target Unix time: {unix_time} ({unix_datetime.isoformat()})")
                    
                if 'target_time_sim' in output_data:
                    sim_time = output_data['target_time_sim']
                    print(f"  Target sim time: {sim_time}")
                    
                if 'target_time_iso' in output_data:
                    iso_time = output_data['target_time_iso']
                    print(f"  Target ISO time: {iso_time}")
                
                print(f"  Epoch: {env.epoch.isoformat()}")
                print("-" * 50)
    
    # Add processes to the environment
    env.process(input_process())
    env.process(output_process())
    
    # Run the simulation
    print(f"Starting simulation with epoch: {env.epoch.isoformat()}")
    print(f"Epoch Unix timestamp: {env.epoch.timestamp()}")
    print("=" * 60)
    
    env.run(until=100)

def test_time_calculations():
    """Test the time calculation logic separately"""
    
    print("\n" + "=" * 60)
    print("TESTING TIME CALCULATION LOGIC")
    print("=" * 60)
    
    # Set up test epoch
    epoch = datetime(2023, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
    current_sim_time = 1800  # 30 minutes into simulation
    
    print(f"Epoch: {epoch.isoformat()}")
    print(f"Epoch Unix timestamp: {epoch.timestamp()}")
    print(f"Current sim time: {current_sim_time} seconds")
    
    # Test cases for Unix time
    unix_test_cases = [
        ("1 hour after epoch", epoch.timestamp() + 3600),
        ("2 hours after epoch", epoch.timestamp() + 7200),
        ("30 minutes before epoch", epoch.timestamp() - 1800),
        ("Current time in Unix", epoch.timestamp() + current_sim_time),
    ]
    
    # Test cases for ISO datetime
    iso_test_cases = [
        ("1 hour after epoch", (epoch + timedelta(hours=1)).isoformat()),
        ("2 hours after epoch", (epoch + timedelta(hours=2)).isoformat()),
        ("30 minutes before epoch", (epoch - timedelta(minutes=30)).isoformat()),
        ("Current time in ISO", (epoch + timedelta(seconds=current_sim_time)).isoformat()),
        ("ISO with Z suffix", (epoch + timedelta(hours=1.5)).isoformat() + "Z"),
    ]
    
    print("\nUnix Time Test Cases:")
    print("-" * 30)
    for description, unix_time in unix_test_cases:
        unix_datetime = datetime.fromtimestamp(unix_time, tz=timezone.utc)
        time_delta = unix_datetime - epoch
        time_delay_sim_time_secs = time_delta.total_seconds()
        delay = time_delay_sim_time_secs - current_sim_time
        
        print(f"\nTest: {description}")
        print(f"  Unix time: {unix_time}")
        print(f"  Unix datetime: {unix_datetime.isoformat()}")
        print(f"  Time delta from epoch: {time_delta.total_seconds()} seconds")
        print(f"  Sim time equivalent: {time_delay_sim_time_secs} seconds")
        print(f"  Delay from current sim time: {delay} seconds")
        if delay < 0:
            print(f"  WARNING: Negative delay!")
    
    print("\nISO Datetime Test Cases:")
    print("-" * 30)
    for description, iso_time in iso_test_cases:
        # Handle Z suffix
        iso_time_clean = iso_time.replace('Z', '+00:00')
        iso_datetime = datetime.fromisoformat(iso_time_clean)
        if iso_datetime.tzinfo is None:
            iso_datetime = iso_datetime.replace(tzinfo=timezone.utc)
        time_delta = iso_datetime - epoch
        time_delay_sim_time_secs = time_delta.total_seconds()
        delay = time_delay_sim_time_secs - current_sim_time
        
        print(f"\nTest: {description}")
        print(f"  ISO time: {iso_time}")
        print(f"  ISO datetime: {iso_datetime.isoformat()}")
        print(f"  Time delta from epoch: {time_delta.total_seconds()} seconds")
        print(f"  Sim time equivalent: {time_delay_sim_time_secs} seconds")
        print(f"  Delay from current sim time: {delay} seconds")
        if delay < 0:
            print(f"  WARNING: Negative delay!")

if __name__ == "__main__":
    test_keydelaytime_unix_conversion()
    test_time_calculations()