#!/usr/bin/env python3
import os
import time
import json
import uuid
import argparse
import logging
from pulsar import Client, Producer, MessageId

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("pulsar-producer")

def generate_test_message(sequence_number):
    """Generate a sample test message with timestamp and sequence number."""
    return {
        "message_id": str(uuid.uuid4()),
        "timestamp": time.time(),
        "sequence": sequence_number,
        "content": f"Test message #{sequence_number}",
        "metadata": {
            "source": "test-producer",
            "type": "test"
        }
    }

def create_producer(client, topic_name):
    """Create and return a Pulsar producer."""
    try:
        return client.create_producer(
            topic=topic_name,
            producer_name="test-producer",
            schema=None,  # Use raw bytes for maximum flexibility
        )
    except Exception as e:
        logger.error(f"Failed to create producer: {e}")
        raise

def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Pulsar Test Message Producer')
    parser.add_argument('--broker-url', type=str, 
                        default=os.environ.get('PULSAR_BROKER_URL', 'pulsar://pulsar-broker:6650'),
                        help='Pulsar broker URL')
    parser.add_argument('--topic', type=str, required=True,
                        help='Topic to produce messages to')
    parser.add_argument('--num-messages', type=int, default=10,
                        help='Number of messages to produce')
    parser.add_argument('--interval', type=float, default=1.0,
                        help='Interval between messages in seconds')
    parser.add_argument('--batch', action='store_true',
                        help='Send messages in batch mode without waiting')
    args = parser.parse_args()
    
    logger.info(f"Connecting to Pulsar broker at {args.broker_url}")
    client = Client(args.broker_url)
    
    try:
        producer = create_producer(client, args.topic)
        logger.info(f"Producer created for topic: {args.topic}")
        
        for i in range(1, args.num_messages + 1):
            message = generate_test_message(i)
            message_data = json.dumps(message).encode('utf-8')
            
            # Send message
            msg_id = producer.send(message_data)
            logger.info(f"Sent message #{i}/{args.num_messages} with ID: {MessageId.deserialize(msg_id)}")
            
            # Wait between messages unless batch mode is enabled
            if not args.batch and i < args.num_messages:
                time.sleep(args.interval)
        
        logger.info(f"Successfully sent {args.num_messages} messages to {args.topic}")
        
    except Exception as e:
        logger.error(f"Error during message production: {e}")
    finally:
        # Clean up resources
        producer.close()
        client.close()
        logger.info("Producer closed")

if __name__ == "__main__":
    main()