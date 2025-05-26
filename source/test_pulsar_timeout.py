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
            # Create Pulsar client and consumer
            client = pulsar.Client(pulsar_server)
            consumer = client.subscribe(
                topic_name,
                subscription_name=f"test-sub-{int(time.time())}",
                subscription_type=pulsar.SubscriptionType.Exclusive
            )
            
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
            print(f"✗ Error setting up Pulsar client: {e}")
            print("  Make sure Pulsar is running on localhost:6650")
        
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

if __name__ == "__main__":
    print("Pulsar Timeout Test Script")
    print("This script tests the timeout functionality of PulsarTopicSource")
    print("Make sure Pulsar is running on localhost:6650 before running this test")
    print()
    
    try:
        # Test timeout behavior with no messages
        test_pulsar_timeout()
        
        # Test normal operation with messages
        test_pulsar_with_messages()
        
    except KeyboardInterrupt:
        print("\nTest interrupted by user")
    except Exception as e:
        print(f"Test failed with error: {e}")
    
    print("\nTest completed")