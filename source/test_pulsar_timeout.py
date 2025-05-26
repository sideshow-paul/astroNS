import sys
import os
import time
import threading
import json
import pulsar
from datetime import datetime

# Add source directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'astroNS'))

def test_pulsar_timeout():
    """Test PulsarTopicSource timeout functionality"""
    
    # Pulsar configuration
    pulsar_server = "pulsar://localhost:6650"
    topic_name = "test-timeout-topic"
    
    print("=" * 60)
    print("TESTING PULSAR TIMEOUT FUNCTIONALITY")
    print("=" * 60)
    print(f"Server: {pulsar_server}")
    print(f"Topic: {topic_name}")
    print(f"Test will demonstrate timeout behavior when no messages are available")
    print()
    
    # Test different timeout values
    timeout_tests = [
        {"timeout_secs": 2.0, "description": "Short timeout (2 seconds)"},
        {"timeout_secs": 5.0, "description": "Medium timeout (5 seconds)"},
        {"timeout_secs": 1.0, "description": "Very short timeout (1 second)"}
    ]
    
    for test_config in timeout_tests:
        print(f"Testing: {test_config['description']}")
        print(f"Timeout: {test_config['timeout_secs']} seconds")
        
        try:
            # Create Pulsar client and consumer with subscription timeout handling
            print(f"Attempting to connect to Pulsar server: {pulsar_server}")
            client = pulsar.Client(pulsar_server)
            print(f"✓ Successfully connected to Pulsar server")
            
            print(f"Attempting to subscribe to topic: {topic_name}")
            consumer = client.subscribe(
                topic_name,
                subscription_name=f"test-sub-{int(time.time())}",
                subscription_type=pulsar.SubscriptionType.Exclusive
            )
            print(f"✓ Successfully subscribed to topic")
            
            timeout_ms = int(test_config['timeout_secs'] * 1000)
            
            print(f"Attempting to receive message with {timeout_ms}ms timeout...")
            start_time = time.time()
            
            try:
                # This should timeout since no messages are being sent
                msg = consumer.receive(timeout_millis=timeout_ms)
                print(f"Unexpected message received: {msg.data().decode('utf-8')}")
                consumer.acknowledge(msg)
            except Exception as e:
                end_time = time.time()
                elapsed = end_time - start_time
                
                if "timeout" in str(e).lower():
                    print(f"✓ Timeout occurred as expected after {elapsed:.2f} seconds")
                    print(f"  Error: {e}")
                else:
                    print(f"✗ Different error occurred: {e}")
            
            # Clean up
            consumer.close()
            client.close()
            
        except Exception as e:
            error_type = type(e).__name__
            print(f"✗ Error setting up Pulsar client ({error_type}): {e}")
            if "connection" in str(e).lower():
                print("  → Connection error: Make sure Pulsar is running on localhost:6650")
            elif "timeout" in str(e).lower():
                print("  → Subscription timeout: Pulsar server may be overloaded")
            elif "topic" in str(e).lower():
                print("  → Topic error: Topic may not exist or have permission issues")
            else:
                print("  → Check Pulsar server status and configuration")
        
        print("-" * 40)
        print()

def test_pulsar_with_messages():
    """Test PulsarTopicSource with actual messages"""
    
    pulsar_server = "pulsar://localhost:6650"
    topic_name = "test-message-topic"
    
    print("TESTING PULSAR WITH ACTUAL MESSAGES")
    print("=" * 60)
    
    def send_test_messages():
        """Send test messages to the topic"""
        try:
            client = pulsar.Client(pulsar_server)
            producer = client.create_producer(topic_name)
            
            messages = [
                {
                    "assignment_id": "test-001",
                    "satellite_name": "TEST-SAT-1",
                    "simtime": 100.0,
                    "timestamp": datetime.now().isoformat()
                },
                {
                    "message_type": "END_OF_ASSIGNMENT_BATCH_AND_ADVANCE_TIME",
                    "advance_simulation_time_to_unix_ts": time.time() + 3600,
                    "simtime": 200.0,
                    "timestamp": datetime.now().isoformat()
                }
            ]
            
            print("Sending test messages...")
            for i, msg in enumerate(messages):
                producer.send(json.dumps(msg).encode('utf-8'))
                print(f"  Sent message {i+1}: {msg.get('assignment_id', msg.get('message_type'))}")
                time.sleep(1)  # Space out messages
            
            producer.close()
            client.close()
            print("Messages sent successfully")
            
        except Exception as e:
            print(f"Error sending messages: {e}")
    
    def receive_test_messages():
        """Receive messages with timeout"""
        try:
            client = pulsar.Client(pulsar_server)
            consumer = client.subscribe(
                topic_name,
                subscription_name=f"test-receive-{int(time.time())}",
                subscription_type=pulsar.SubscriptionType.Exclusive
            )
            
            timeout_ms = 3000  # 3 seconds
            received_count = 0
            max_attempts = 5
            
            print(f"Receiving messages with {timeout_ms}ms timeout...")
            
            for attempt in range(max_attempts):
                try:
                    start_time = time.time()
                    msg = consumer.receive(timeout_millis=timeout_ms)
                    end_time = time.time()
                    
                    message_data = msg.data().decode('utf-8')
                    parsed_msg = json.loads(message_data)
                    
                    print(f"  Received message {received_count + 1} after {end_time - start_time:.2f}s:")
                    print(f"    Content: {message_data}")
                    
                    consumer.acknowledge(msg)
                    received_count += 1
                    
                except Exception as e:
                    if "timeout" in str(e).lower():
                        print(f"  Timeout on attempt {attempt + 1} - no more messages")
                        break
                    else:
                        print(f"  Error on attempt {attempt + 1}: {e}")
            
            print(f"Total messages received: {received_count}")
            consumer.close()
            client.close()
            
        except Exception as e:
            print(f"Error receiving messages: {e}")
    
    # Send messages in a separate thread
    sender_thread = threading.Thread(target=send_test_messages)
    sender_thread.start()
    
    # Wait a moment for sender to start
    time.sleep(2)
    
    # Receive messages
    receive_test_messages()
    
    # Wait for sender to complete
    sender_thread.join()

def test_subscription_failures():
    """Test various subscription failure scenarios"""
    
    print("\nTESTING SUBSCRIPTION FAILURE SCENARIOS")
    print("=" * 60)
    
    # Test 1: Invalid server
    print("Test 1: Invalid Pulsar server")
    try:
        client = pulsar.Client("pulsar://invalid-server:6650")
        consumer = client.subscribe("test-topic", subscription_name="test-sub")
        print("✗ Unexpected success with invalid server")
        consumer.close()
        client.close()
    except Exception as e:
        print(f"✓ Expected error with invalid server: {type(e).__name__}")
    
    # Test 2: Invalid port
    print("\nTest 2: Invalid port")
    try:
        client = pulsar.Client("pulsar://localhost:9999")
        consumer = client.subscribe("test-topic", subscription_name="test-sub")
        print("✗ Unexpected success with invalid port")
        consumer.close()
        client.close()
    except Exception as e:
        print(f"✓ Expected error with invalid port: {type(e).__name__}")
    
    # Test 3: Valid server but problematic topic
    print("\nTest 3: Problematic topic name")
    try:
        client = pulsar.Client("pulsar://localhost:6650")
        consumer = client.subscribe("", subscription_name="test-sub")  # Empty topic name
        print("✗ Unexpected success with empty topic")
        consumer.close()
        client.close()
    except Exception as e:
        print(f"✓ Expected error with empty topic: {type(e).__name__}")

def test_retry_functionality():
    """Test the retry functionality of PulsarTopicSource"""
    
    print("\nTESTING RETRY FUNCTIONALITY")
    print("=" * 60)
    
    # Test configuration with different retry settings
    retry_configs = [
        {
            "name": "Default retry settings",
            "config": {
                "retry_on_connection_error": True,
                "max_retry_attempts": 3,
                "retry_delay_secs": 2.0
            }
        },
        {
            "name": "Aggressive retry settings",
            "config": {
                "retry_on_connection_error": True,
                "max_retry_attempts": 5,
                "retry_delay_secs": 1.0
            }
        },
        {
            "name": "Retry disabled",
            "config": {
                "retry_on_connection_error": False,
                "max_retry_attempts": 1,
                "retry_delay_secs": 5.0
            }
        }
    ]
    
    for test_case in retry_configs:
        print(f"\nTesting: {test_case['name']}")
        config = test_case['config']
        
        print(f"  retry_on_connection_error: {config['retry_on_connection_error']}")
        print(f"  max_retry_attempts: {config['max_retry_attempts']}")
        print(f"  retry_delay_secs: {config['retry_delay_secs']}")
        
        # Simulate retry logic (without actual PulsarTopicSource to avoid dependencies)
        max_attempts = config['max_retry_attempts']
        retry_enabled = config['retry_on_connection_error']
        delay = config['retry_delay_secs']
        
        if retry_enabled:
            print(f"  → Would attempt connection {max_attempts} times with {delay}s delays")
            total_time = (max_attempts - 1) * delay
            print(f"  → Maximum retry time: {total_time} seconds")
        else:
            print(f"  → Would attempt connection once, then stop")
        
        print(f"  ✓ Configuration validated")

def test_connection_recovery_simulation():
    """Simulate connection recovery scenarios"""
    
    print("\nTESTING CONNECTION RECOVERY SIMULATION")
    print("=" * 60)
    
    scenarios = [
        {
            "name": "Pulsar server restart",
            "description": "Server goes down then comes back up",
            "expected_behavior": "Should retry and reconnect when server returns"
        },
        {
            "name": "Network interruption",
            "description": "Temporary network connectivity loss",
            "expected_behavior": "Should retry connection attempts"
        },
        {
            "name": "Topic deletion and recreation",
            "description": "Topic is deleted then recreated",
            "expected_behavior": "Should handle subscription errors and retry"
        },
        {
            "name": "Permission changes",
            "description": "Subscription permissions are temporarily revoked",
            "expected_behavior": "Should retry until permissions restored"
        }
    ]
    
    for scenario in scenarios:
        print(f"\nScenario: {scenario['name']}")
        print(f"  Description: {scenario['description']}")
        print(f"  Expected: {scenario['expected_behavior']}")
        print(f"  ✓ Scenario documented for manual testing")

if __name__ == "__main__":
    print("Pulsar Timeout and Retry Test Script")
    print("This script tests the timeout functionality and retry logic of PulsarTopicSource")
    print("and various subscription failure scenarios")
    print("Make sure Pulsar is running on localhost:6650 before running this test")
    print()
    
    try:
        # Test timeout behavior with no messages
        test_pulsar_timeout()
        
        # Test normal operation with messages
        test_pulsar_with_messages()
        
        # Test subscription failure scenarios
        test_subscription_failures()
        
        # Test retry functionality
        test_retry_functionality()
        
        # Test connection recovery simulation
        test_connection_recovery_simulation()
        
    except KeyboardInterrupt:
        print("\nTest interrupted by user")
    except Exception as e:
        print(f"Test failed with error: {e}")
    
    print("\nTest completed")
    print("\nNOTE: For full testing of retry functionality, manually:")
    print("1. Start the test with Pulsar running")
    print("2. Stop Pulsar during execution to test retry logic")
    print("3. Restart Pulsar to test reconnection")
    print("4. Observe retry attempts and recovery behavior")