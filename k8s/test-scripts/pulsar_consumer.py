#!/usr/bin/env python3
import os
import time
import json
import argparse
import logging
from pulsar import Client, ConsumerType

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("pulsar-consumer")

def create_consumer(client, topic_name, subscription_name, consumer_type):
    """Create and return a Pulsar consumer."""
    try:
        consumer_type_map = {
            "exclusive": ConsumerType.Exclusive,
            "shared": ConsumerType.Shared,
            "failover": ConsumerType.Failover
        }
        return client.subscribe(
            topic=topic_name,
            subscription_name=subscription_name,
            consumer_type=consumer_type_map.get(consumer_type, ConsumerType.Shared)
        )
    except Exception as e:
        logger.error(f"Failed to create consumer: {e}")
        raise

def process_message(msg):
    """Process a received message and return parsed JSON content."""
    try:
        # Attempt to parse as JSON
        data = json.loads(msg.data().decode('utf-8'))
        return data
    except json.JSONDecodeError:
        # Handle non-JSON messages
        return {"raw_data": msg.data().decode('utf-8', errors='replace')}
    except Exception as e:
        logger.error(f"Error processing message: {e}")
        return {"error": str(e)}

def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Pulsar Test Message Consumer')
    parser.add_argument('--broker-url', type=str, 
                       default=os.environ.get('PULSAR_BROKER_URL', 'pulsar://pulsar-broker:6650'),
                       help='Pulsar broker URL')
    parser.add_argument('--topic', type=str, required=True,
                       help='Topic to consume messages from')
    parser.add_argument('--subscription', type=str, default='test-subscription',
                       help='Subscription name')
    parser.add_argument('--consumer-type', type=str, default='shared',
                       choices=['exclusive', 'shared', 'failover'],
                       help='Consumer type (exclusive, shared, or failover)')
    parser.add_argument('--timeout', type=int, default=60,
                       help='Time in seconds to consume messages (0 for indefinite)')
    parser.add_argument('--earliest', action='store_true',
                       help='Start consuming from earliest available message')
    args = parser.parse_args()
    
    logger.info(f"Connecting to Pulsar broker at {args.broker_url}")
    client = Client(args.broker_url)
    
    try:
        consumer = create_consumer(client, args.topic, args.subscription, args.consumer_type)
        logger.info(f"Consumer created for topic: {args.topic}, subscription: {args.subscription}")
        
        # Set to earliest if requested
        if args.earliest:
            consumer.seek_earliest()
            logger.info("Seeking to earliest messages")
        
        # Start time for timeout calculation
        start_time = time.time()
        message_count = 0
        
        logger.info(f"Starting to consume messages (timeout: {args.timeout if args.timeout > 0 else 'indefinite'} seconds)")
        
        # Continuously receive messages until timeout
        while True:
            # Check if timeout has been reached
            if args.timeout > 0 and (time.time() - start_time) > args.timeout:
                logger.info(f"Timeout of {args.timeout} seconds reached. Exiting.")
                break
                
            # Try to receive message with a timeout of 1 second
            msg = consumer.receive(timeout_millis=1000)
            if msg:
                message_count += 1
                data = process_message(msg)
                logger.info(f"Received message #{message_count}: {data}")
                
                # Acknowledge the message
                consumer.acknowledge(msg)
            
    except Exception as e:
        if "Pulsar error: TimeOut" in str(e):
            logger.info("No more messages to consume within the timeout period")
        else:
            logger.error(f"Error during message consumption: {e}")
    finally:
        # Clean up resources
        if 'consumer' in locals():
            consumer.close()
        client.close()
        logger.info(f"Consumer closed. Processed {message_count} messages.")

if __name__ == "__main__":
    main()