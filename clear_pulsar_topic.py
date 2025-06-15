#!/usr/bin/env python3
"""
Script to clear all messages from a Pulsar topic.

This script creates a temporary consumer that reads and acknowledges all existing
messages in a topic, effectively clearing it. It handles both persistent and
non-persistent topics.

Usage:
    python clear_pulsar_topic.py <topic_name> [--server <pulsar_server>] [--timeout <seconds>]

Example:
    python clear_pulsar_topic.py persistent://public/default/my-topic
    python clear_pulsar_topic.py my-topic --server pulsar://localhost:6650 --timeout 30
"""

import argparse
import sys
import time
from typing import Optional

try:
    import pulsar
except ImportError:
    print("Error: pulsar-client library not found. Install with: pip install pulsar-client")
    sys.exit(1)


def clear_pulsar_topic(server_url: str, topic_name: str, timeout_seconds: int = 10) -> int:
    """
    Clear all messages from a Pulsar topic.

    Args:
        server_url: Pulsar server URL (e.g., pulsar://localhost:6650)
        topic_name: Name of the topic to clear
        timeout_seconds: Timeout for receive operations in seconds

    Returns:
        Number of messages cleared

    Raises:
        Exception: If connection to Pulsar fails or other errors occur
    """
    client = None
    consumer = None
    messages_cleared = 0

    try:
        # Create Pulsar client
        print(f"Connecting to Pulsar server: {server_url}")
        client = pulsar.Client(server_url)

        # Create a temporary consumer with unique subscription name
        subscription_name = f"clear-topic-{int(time.time())}"
        print(f"Creating consumer for topic: {topic_name}")
        print(f"Using subscription: {subscription_name}")

        consumer = client.subscribe(
            topic=topic_name,
            subscription_name=subscription_name,
            consumer_type=pulsar.ConsumerType.Exclusive,
            initial_position=pulsar.InitialPosition.Earliest
        )

        print(f"Starting to clear messages (timeout: {timeout_seconds}s per message)...")

        # Read and acknowledge all messages until timeout
        while True:
            try:
                # Try to receive a message with timeout
                msg = consumer.receive(timeout_millis=timeout_seconds * 1000)

                # Acknowledge the message (removes it from the topic)
                consumer.acknowledge(msg)
                messages_cleared += 1

                # Print progress every 100 messages
                if messages_cleared % 100 == 0:
                    print(f"Cleared {messages_cleared} messages...")

            except pulsar.Timeout:
                # No more messages available
                print("No more messages to clear (timeout reached)")
                break

        print(f"Successfully cleared {messages_cleared} messages from topic: {topic_name}")
        return messages_cleared

    except Exception as e:
        print(f"Error clearing topic: {e}")
        raise

    finally:
        # Clean up resources
        if consumer:
            try:
                consumer.close()
                print("Consumer closed")
            except Exception as e:
                print(f"Warning: Error closing consumer: {e}")

        if client:
            try:
                client.close()
                print("Client closed")
            except Exception as e:
                print(f"Warning: Error closing client: {e}")


def validate_topic_name(topic_name: str) -> str:
    """
    Validate and normalize topic name.

    Args:
        topic_name: Topic name to validate

    Returns:
        Normalized topic name
    """
    # If topic doesn't start with persistent:// or non-persistent://,
    # assume it's a simple topic name and make it persistent
    if not topic_name.startswith(('persistent://', 'non-persistent://')):
        topic_name = f"persistent://public/default/{topic_name}"
        print(f"Normalized topic name to: {topic_name}")

    return topic_name


def main():
    parser = argparse.ArgumentParser(
        description="Clear all messages from a Pulsar topic",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s persistent://public/default/my-topic
  %(prog)s my-topic --server pulsar://localhost:6650
  %(prog)s my-topic --timeout 30 --server pulsar://pulsar-broker.pulsar:6650
        """
    )

    parser.add_argument(
        "topic_name",
        help="Name of the Pulsar topic to clear"
    )

    parser.add_argument(
        "--server",
        default="pulsar://localhost:6650",
        help="Pulsar server URL (default: pulsar://localhost:6650)"
    )

    parser.add_argument(
        "--timeout",
        type=int,
        default=10,
        help="Timeout in seconds for message receive operations (default: 10)"
    )

    parser.add_argument(
        "--confirm",
        action="store_true",
        help="Skip confirmation prompt and proceed directly"
    )

    args = parser.parse_args()

    # Validate and normalize topic name
    topic_name = validate_topic_name(args.topic_name)

    print(f"Pulsar Topic Cleaner")
    print(f"===================")
    print(f"Server: {args.server}")
    print(f"Topic: {topic_name}")
    print(f"Timeout: {args.timeout}s")
    print()

    # Confirmation prompt (unless --confirm flag is used)
    if not args.confirm:
        response = input(f"Are you sure you want to clear ALL messages from topic '{topic_name}'? (yes/no): ")
        if response.lower() not in ['yes', 'y']:
            print("Operation cancelled.")
            sys.exit(0)

    try:
        # Clear the topic
        start_time = time.time()
        messages_cleared = clear_pulsar_topic(args.server, topic_name, args.timeout)
        end_time = time.time()

        duration = end_time - start_time
        print(f"\nOperation completed successfully!")
        print(f"Messages cleared: {messages_cleared}")
        print(f"Time taken: {duration:.2f} seconds")

        if messages_cleared > 0:
            print(f"Average rate: {messages_cleared/duration:.1f} messages/second")

    except KeyboardInterrupt:
        print("\nOperation interrupted by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\nError: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
