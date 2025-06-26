#!/usr/bin/env python3
"""
Pulsar Listener for SixGeo Simulator Output Messages.

This script listens to a Pulsar topic and decodes messages using the pydantic classes
SimulationStepCompletePayload or CollectedTargetDataPayload wrapped in WrappedOutputMessage.

Usage:
    python pulsar_listener.py <topic_name> [--server <pulsar_server>] [--subscription <subscription_name>]

Example:
    python pulsar_listener.py persistent://twosix/sixgeo/simulation-output
    python pulsar_listener.py my-test-topic --server pulsar://localhost:6650
"""

import argparse
import json
import sys
import signal
from datetime import datetime
from typing import Optional

try:
    import pulsar
except ImportError:
    print("Error: pulsar-client library not found. Install with: pip install pulsar-client")
    sys.exit(1)

# Import the two_six_messages module directly to avoid package import issues
try:
    import os
    import importlib.util

    # Get the path to the two_six_messages.py file
    script_dir = os.path.dirname(os.path.abspath(__file__))
    two_six_messages_path = os.path.join(script_dir, 'source', 'astroNS', 'nodes', 'pydantic_models', 'two_six_messages.py')

    # If not found, try current working directory
    if not os.path.exists(two_six_messages_path):
        two_six_messages_path = os.path.join(os.getcwd(), 'source', 'astroNS', 'nodes', 'pydantic_models', 'two_six_messages.py')

    # Load the module directly
    spec = importlib.util.spec_from_file_location("two_six_messages", two_six_messages_path)
    two_six_messages = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(two_six_messages)

    # Import the classes we need
    WrappedOutputMessage = two_six_messages.WrappedOutputMessage
    OutputMessageType = two_six_messages.OutputMessageType
    SimulationStepCompletePayload = two_six_messages.SimulationStepCompletePayload
    CollectedTargetDataPayload = two_six_messages.CollectedTargetDataPayload

except Exception as e:
    print(f"Error: Could not import pydantic models from two_six_messages.py: {e}")
    print(f"Expected path: {two_six_messages_path if 'two_six_messages_path' in locals() else 'N/A'}")
    print()
    print("Please ensure you're running the script from the astroNS directory")
    print("and that the file source/astroNS/nodes/pydantic_models/two_six_messages.py exists")
    sys.exit(1)


class PulsarListener:
    """Pulsar message listener with graceful shutdown."""

    def __init__(self, server_url: str, topic_name: str, subscription_name: str):
        self.server_url = server_url
        self.topic_name = topic_name
        self.subscription_name = subscription_name
        self.client: Optional[pulsar.Client] = None
        self.consumer: Optional[pulsar.Consumer] = None
        self.running = True

        # Set up signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals."""
        print(f"\nReceived signal {signum}. Shutting down gracefully...")
        self.running = False

    def connect(self):
        """Connect to Pulsar and create consumer."""
        try:
            print(f"Connecting to Pulsar server: {self.server_url}")
            self.client = pulsar.Client(self.server_url)

            print(f"Creating consumer for topic: {self.topic_name}")
            print(f"Subscription: {self.subscription_name}")

            self.consumer = self.client.subscribe(
                topic=self.topic_name,
                subscription_name=self.subscription_name,
                consumer_type=pulsar.ConsumerType.Shared
            )

            print("Successfully connected to Pulsar!")
            print("=" * 60)
            print("Listening for messages... (Press Ctrl+C to stop)")
            print("=" * 60)

        except Exception as e:
            print(f"Error connecting to Pulsar: {e}")
            sys.exit(1)

    def decode_message(self, message_data: bytes) -> Optional[WrappedOutputMessage]:
        """Decode a raw message into a WrappedOutputMessage."""
        try:
            # Parse JSON
            json_data = json.loads(message_data.decode('utf-8'))

            # Create WrappedOutputMessage from JSON
            wrapped_message = WrappedOutputMessage(**json_data)
            return wrapped_message

        except json.JSONDecodeError as e:
            print(f"ERROR: Invalid JSON in message: {e}")
            print(f"Raw message: {message_data}")
            return None
        except Exception as e:
            print(f"ERROR: Failed to decode message: {e}")
            print(f"Raw message: {message_data}")
            return None

    def print_message(self, wrapped_message: WrappedOutputMessage, message_id: str):
        """Print the decoded message in a readable format."""
        timestamp = datetime.now().isoformat()

        print(f"\n[{timestamp}] Message ID: {message_id}")
        print(f"Message Type: {wrapped_message.message_type}")
        print("-" * 40)

        if wrapped_message.message_type == OutputMessageType.SIMULATION_STEP_COMPLETE:
            payload = wrapped_message.payload
            print(f"TimeStepEndTime: {payload.TimeStepEndTime}")
            print(f"Status: {payload.Status}")
            if payload.Message:
                print(f"Message: {payload.Message}")

        elif wrapped_message.message_type == OutputMessageType.COLLECTED_TARGET_DATA:
            payload = wrapped_message.payload
            print(f"Collected Target Data ID: {payload.collected_target_data_id}")
            print(f"Assignment ID: {payload.assignment_id}")
            print(f"Opportunity ID: {payload.opportunity_id}")
            print(f"Task ID: {payload.task_id}")
            print(f"Target ID: {payload.target_id}")
            print(f"Satellite Name: {payload.satellite_name}")
            print(f"Agent ID: {payload.agent_id}")
            print(f"Collection Start: {payload.actual_collection_start_time}")
            print(f"Collection End: {payload.actual_collection_end_time}")
            print(f"Aimpoint: ({payload.aimpoint_latitude}, {payload.aimpoint_longitude})")
            print(f"Success Status: {payload.simulated_success_status}")

            if payload.failure_reason:
                print(f"Failure Reason: {payload.failure_reason}")
            if payload.simulated_quality_score is not None:
                print(f"Quality Score: {payload.simulated_quality_score}")
            if payload.simulated_gsd_cm is not None:
                print(f"GSD (cm): {payload.simulated_gsd_cm}")
            if payload.simulated_cloud_cover_percent is not None:
                print(f"Cloud Cover (%): {payload.simulated_cloud_cover_percent}")
            if payload.simulated_area_covered_sqkm is not None:
                print(f"Area Covered (sq km): {payload.simulated_area_covered_sqkm}")
            if payload.collected_metrics:
                print(f"Collected Metrics: {json.dumps(payload.collected_metrics, indent=2)}")
            if payload.additional_sim_metadata:
                print(f"Additional Metadata: {json.dumps(payload.additional_sim_metadata, indent=2)}")
            if payload.notes_from_simulator:
                print(f"Simulator Notes: {payload.notes_from_simulator}")

        print("=" * 60)

    def listen(self):
        """Main listening loop."""
        if not self.consumer:
            raise RuntimeError("Consumer not initialized. Call connect() first.")

        message_count = 0

        try:
            while self.running:
                try:
                    # Receive message with timeout
                    msg = self.consumer.receive(timeout_millis=1000)
                    message_count += 1

                    # Decode the message
                    wrapped_message = self.decode_message(msg.data())

                    if wrapped_message:
                        # Print the decoded message
                        self.print_message(wrapped_message, str(msg.message_id()))

                        # Acknowledge the message
                        self.consumer.acknowledge(msg)
                    else:
                        print(f"Failed to decode message {message_count}, acknowledging anyway...")
                        self.consumer.acknowledge(msg)

                except pulsar.Timeout:
                    # Timeout is expected, just continue
                    continue
                except Exception as e:
                    print(f"ERROR processing message: {e}")
                    continue

        except KeyboardInterrupt:
            print("\nReceived keyboard interrupt")
        finally:
            print(f"\nProcessed {message_count} messages total")
            self.cleanup()

    def cleanup(self):
        """Clean up resources."""
        try:
            if self.consumer:
                print("Closing consumer...")
                self.consumer.close()
            if self.client:
                print("Closing client...")
                self.client.close()
            print("Cleanup completed")
        except Exception as e:
            print(f"Error during cleanup: {e}")


def main():
    parser = argparse.ArgumentParser(
        description="Listen to Pulsar topic and decode SixGeo Simulator output messages",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s persistent://twosix/sixgeo/simulation-output
  %(prog)s my-test-topic --server pulsar://localhost:6650
  %(prog)s my-topic --subscription my-subscription
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
        default="listener-subscription",
        help="Pulsar subscription name (default: listener-subscription)"
    )

    args = parser.parse_args()

    print(f"SixGeo Simulator Output Message Listener")
    print(f"========================================")
    print(f"Topic: {args.topic_name}")
    print(f"Server: {args.server}")
    print(f"Subscription: {args.subscription}")
    print()

    # Create and start listener
    listener = PulsarListener(args.server, args.topic_name, args.subscription)
    listener.connect()
    listener.listen()


if __name__ == "__main__":
    main()
