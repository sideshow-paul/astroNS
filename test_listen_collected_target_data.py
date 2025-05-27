#!/usr/bin/env python3
"""
Test script to listen to a Pulsar topic and validate CollectedTargetData messages.

Usage:
    python test_listen_collected_target_data.py <topic_name> [--server <pulsar_server>] [--subscription <sub_name>]

Example:
    python test_listen_collected_target_data.py persistent://twosix/sixgeo/collected-target-data
    python test_listen_collected_target_data.py my-test-topic --server pulsar://localhost:6650 --subscription test-sub
"""

import argparse
import json
import sys
import signal
from typing import Dict, Any

try:
    import pulsar
except ImportError:
    print("Error: pulsar-client library not found. Install with: pip install pulsar-client")
    sys.exit(1)

try:
    from pydantic import ValidationError
    from nodes.pydantic_models.simulator_interfaces import CollectedTargetData
except ImportError:
    print("Error: Required modules not found. Make sure you're running from the correct directory with access to nodes.pydantic_models")
    sys.exit(1)


class CollectedTargetDataListener:
    def __init__(self, server_url: str, topic_name: str, subscription_name: str):
        self.server_url = server_url
        self.topic_name = topic_name
        self.subscription_name = subscription_name
        self.client = None
        self.consumer = None
        self.running = False
        self.message_count = 0
        self.success_count = 0
        self.failure_count = 0
        
    def connect(self):
        """Connect to Pulsar and create consumer."""
        try:
            print(f"Connecting to Pulsar server: {self.server_url}")
            self.client = pulsar.Client(self.server_url)
            
            print(f"Creating consumer for topic: {self.topic_name}")
            print(f"Using subscription: {self.subscription_name}")
            self.consumer = self.client.subscribe(
                topic=self.topic_name,
                subscription_name=self.subscription_name
            )
            print("Successfully connected and subscribed!")
            return True
            
        except Exception as e:
            print(f"Error connecting to Pulsar: {e}")
            return False
    
    def validate_message(self, message_data: Dict[str, Any]) -> bool:
        """Validate message against CollectedTargetData schema."""
        try:
            # Attempt to create CollectedTargetData object
            collected_data = CollectedTargetData(**message_data)
            
            # If we get here, validation succeeded
            print(f"✅ SUCCESS: Valid CollectedTargetData object created")
            print(f"   - collected_target_data_id: {collected_data.collected_target_data_id}")
            print(f"   - assignment_id: {collected_data.assignment_id}")
            print(f"   - satellite_name: {collected_data.satellite_name}")
            print(f"   - success_status: {collected_data.simulated_success_status}")
            if collected_data.failure_reason:
                print(f"   - failure_reason: {collected_data.failure_reason}")
            if collected_data.simulated_quality_score is not None:
                print(f"   - quality_score: {collected_data.simulated_quality_score}")
            
            return True
            
        except ValidationError as e:
            print(f"❌ VALIDATION ERROR: Failed to create CollectedTargetData object")
            print(f"   Validation errors:")
            for error in e.errors():
                field = " -> ".join(str(x) for x in error['loc'])
                print(f"     - {field}: {error['msg']}")
            return False
            
        except Exception as e:
            print(f"❌ UNEXPECTED ERROR: {e}")
            return False
    
    def process_message(self, msg):
        """Process a single message."""
        self.message_count += 1
        
        try:
            # Decode message
            message_content = msg.data().decode('utf-8')
            print(f"\n📨 Message #{self.message_count} received:")
            print(f"Raw content: {message_content}")
            
            # Parse JSON
            try:
                message_data = json.loads(message_content)
            except json.JSONDecodeError as e:
                print(f"❌ JSON PARSE ERROR: {e}")
                self.failure_count += 1
                return
            
            # Validate against CollectedTargetData schema
            if self.validate_message(message_data):
                self.success_count += 1
            else:
                self.failure_count += 1
                
        except Exception as e:
            print(f"❌ MESSAGE PROCESSING ERROR: {e}")
            self.failure_count += 1
    
    def listen(self):
        """Start listening for messages."""
        if not self.connect():
            return
        
        self.running = True
        print(f"\n🎧 Listening for messages on topic: {self.topic_name}")
        print("Press Ctrl+C to stop...\n")
        
        try:
            while self.running:
                try:
                    # Receive message with timeout
                    msg = self.consumer.receive(timeout_millis=1000)
                    
                    # Process message
                    self.process_message(msg)
                    
                    # Acknowledge message
                    self.consumer.acknowledge(msg)
                    
                except Exception as e:
                    if "timeout" not in str(e).lower():
                        print(f"Error receiving message: {e}")
                    # Continue listening even on errors
                    
        except KeyboardInterrupt:
            print("\n\n🛑 Stopping listener...")
        
        finally:
            self.cleanup()
    
    def cleanup(self):
        """Clean up connections."""
        print(f"\n📊 Final Statistics:")
        print(f"   Total messages: {self.message_count}")
        print(f"   Successful validations: {self.success_count}")
        print(f"   Failed validations: {self.failure_count}")
        if self.message_count > 0:
            success_rate = (self.success_count / self.message_count) * 100
            print(f"   Success rate: {success_rate:.1f}%")
        
        try:
            if self.consumer:
                self.consumer.close()
                print("Consumer closed")
        except Exception as e:
            print(f"Error closing consumer: {e}")
        
        try:
            if self.client:
                self.client.close()
                print("Client closed")
        except Exception as e:
            print(f"Error closing client: {e}")


def signal_handler(sig, frame):
    """Handle Ctrl+C gracefully."""
    print("\n🛑 Received interrupt signal...")
    sys.exit(0)


def main():
    # Set up signal handler for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    
    parser = argparse.ArgumentParser(
        description="Listen to a Pulsar topic and validate CollectedTargetData messages",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s persistent://twosix/sixgeo/collected-target-data
  %(prog)s my-test-topic --server pulsar://localhost:6650
  %(prog)s my-topic --subscription custom-sub
        """
    )
    
    parser.add_argument(
        "topic_name",
        help="Name of the Pulsar topic to listen to"
    )
    
    parser.add_argument(
        "--server",
        default="pulsar://localhost:6650",
        help="Pulsar server URL (default: pulsar://localhost:6650)"
    )
    
    parser.add_argument(
        "--subscription",
        default="test-listener",
        help="Subscription name (default: test-listener)"
    )
    
    args = parser.parse_args()
    
    print(f"CollectedTargetData Message Listener")
    print(f"===================================")
    print(f"Topic: {args.topic_name}")
    print(f"Server: {args.server}")
    print(f"Subscription: {args.subscription}")
    print()
    
    # Create listener and start listening
    listener = CollectedTargetDataListener(args.server, args.topic_name, args.subscription)
    listener.listen()


if __name__ == "__main__":
    main()