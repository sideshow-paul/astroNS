#!/usr/bin/env python3
"""
Test script to send TaskAssignment test data to a Pulsar topic.

Usage:
    python test_send_task_assignments.py <topic_name> [--server <pulsar_server>] [--file <json_file>] [--update_timestamps]

Example:
    python test_send_task_assignments.py persistent://twosix/sixgeo/task-assignments
    python test_send_task_assignments.py my-test-topic --server pulsar://localhost:6650
    python test_send_task_assignments.py my-topic --update_timestamps
"""

import argparse
import json
import sys
import time
import datetime
from pathlib import Path
from typing import List, Dict, Any

try:
    import pulsar
except ImportError:
    print("Error: pulsar-client library not found. Install with: pip install pulsar-client")
    sys.exit(1)


def load_test_data(file_path: str) -> List[Dict[str, Any]]:
    """Load test data from JSON file."""
    try:
        with open(file_path, 'r') as f:
            data = json.load(f)

        if not isinstance(data, list):
            raise ValueError("JSON file must contain an array of objects")

        print(f"Loaded {len(data)} test objects from {file_path}")
        return data

    except FileNotFoundError:
        print(f"Error: File {file_path} not found")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in {file_path}: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Error loading file {file_path}: {e}")
        sys.exit(1)


def update_timestamps(data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Update timestamps in test data to current time."""
    if not data or "timestamp" not in data[0]:
        print("Warning: No timestamp field found in first record, skipping timestamp updates")
        return data

    try:
        # Parse the first timestamp
        first_timestamp = datetime.datetime.fromisoformat(data[0]["timestamp"].replace("Z", "+00:00"))
        # Get current time in UTC
        current_time = datetime.datetime.now(datetime.timezone.utc)
        # Calculate time delta
        time_delta = current_time - first_timestamp

        print(f"Updating timestamps by adding {time_delta}")

        # Update all timestamps
        updated_data = []
        for item in data:
            if "timestamp" in item:
                original_timestamp = datetime.datetime.fromisoformat(item["timestamp"].replace("Z", "+00:00"))
                new_timestamp = original_timestamp + time_delta
                item["timestamp"] = new_timestamp.isoformat().replace("+00:00", "Z")
            updated_data.append(item)

        return updated_data

    except Exception as e:
        print(f"Error updating timestamps: {e}")
        print("Continuing with original timestamps")
        return data


def send_to_pulsar(server_url: str, topic_name: str, test_data: List[Dict[str, Any]], delay: float = 1.0):
    """Send test data to Pulsar topic."""
    try:
        # Create Pulsar client
        print(f"Connecting to Pulsar server: {server_url}")
        client = pulsar.Client(server_url)

        # Create producer
        print(f"Creating producer for topic: {topic_name}")
        producer = client.create_producer(topic_name)

        # Send each message
        for i, data in enumerate(test_data, 1):
            try:
                message_json = json.dumps(data)
                producer.send(message_json.encode('utf-8'))
                print(f"Sent message {i}/{len(test_data)}: assignment_id={data.get('assignment_id', 'unknown')}")

                # Add delay between messages to avoid overwhelming the system
                if delay > 0 and i < len(test_data):
                    time.sleep(delay)

            except Exception as e:
                print(f"Error sending message {i}: {e}")
                continue

        print(f"Successfully sent {len(test_data)} messages to topic {topic_name}")

        # Cleanup
        producer.close()
        client.close()

    except Exception as e:
        print(f"Error connecting to Pulsar or sending messages: {e}")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="Send TaskAssignment test data to a Pulsar topic",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s persistent://twosix/sixgeo/task-assignments
  %(prog)s my-test-topic --server pulsar://localhost:6650
  %(prog)s my-topic --file custom_test_data.json --delay 0.5
        """
    )

    parser.add_argument(
        "topic_name",
        help="Name of the Pulsar topic to send messages to"
    )

    parser.add_argument(
        "--server",
        default="pulsar://localhost:6650",
        help="Pulsar server URL (default: pulsar://localhost:6650)"
    )

    parser.add_argument(
        "--file",
        default="test_task_assignments.json",
        help="Path to JSON file containing test data (default: test_task_assignments.json)"
    )

    parser.add_argument(
        "--delay",
        type=float,
        default=1.0,
        help="Delay in seconds between sending messages (default: 1.0)"
    )

    parser.add_argument(
        "--update_timestamps",
        action="store_true",
        help="Update timestamps in test data to current time"
    )

    args = parser.parse_args()

    # Resolve file path relative to script location
    script_dir = Path(__file__).parent
    file_path = script_dir / args.file

    print(f"TaskAssignment Test Data Sender")
    print(f"==============================")
    print(f"Topic: {args.topic_name}")
    print(f"Server: {args.server}")
    print(f"File: {file_path}")
    print(f"Delay: {args.delay}s")
    print(f"Update timestamps: {args.update_timestamps}")
    print()

    # Load test data
    test_data = load_test_data(str(file_path))

    # Update timestamps if requested
    if args.update_timestamps:
        test_data = update_timestamps(test_data)

    # Send to Pulsar
    send_to_pulsar(args.server, args.topic_name, test_data, args.delay)

    print("Test data sending completed!")


if __name__ == "__main__":
    main()
