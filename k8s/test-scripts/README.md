# Pulsar Test Scripts for Kubernetes

This directory contains scripts and configurations for testing Apache Pulsar using a Python client in a Kubernetes environment.

## Contents

- `pulsar_producer.py`: Python script to produce messages to a Pulsar topic
- `pulsar_consumer.py`: Python script to consume messages from a Pulsar topic
- `pulsar-test-pod.yaml`: Kubernetes pod configuration for running the test scripts

## Prerequisites

- A running Kubernetes cluster
- Apache Pulsar deployed in the cluster (using `../pulsar.yaml` and `../pulsar-config.yaml`)
- kubectl configured to access your cluster

## Deployment

1. Deploy the Pulsar test client pod:

```bash
kubectl apply -f pulsar-test-pod.yaml
```

2. Verify the pod is running:

```bash
kubectl get pods -n pulsar | grep pulsar-test-client
```

## Usage

### Producing Messages

To produce messages to a Pulsar topic, use the following command:

```bash
kubectl exec -it -n pulsar pulsar-test-client -- python /app/scripts/pulsar_producer.py --topic persistent://public/default/test-topic --num-messages 10
```

Options:
- `--topic`: The topic to produce messages to (required)
- `--broker-url`: Pulsar broker URL (default: pulsar://pulsar-broker:6650)
- `--num-messages`: Number of messages to produce (default: 10)
- `--interval`: Interval between messages in seconds (default: 1.0)
- `--batch`: Send messages in batch mode without waiting

### Consuming Messages

To consume messages from a Pulsar topic, use the following command:

```bash
kubectl exec -it -n pulsar pulsar-test-client -- python /app/scripts/pulsar_consumer.py --topic persistent://public/default/test-topic
```

Options:
- `--topic`: The topic to consume messages from (required)
- `--broker-url`: Pulsar broker URL (default: pulsar://pulsar-broker:6650)
- `--subscription`: Subscription name (default: test-subscription)
- `--consumer-type`: Consumer type: exclusive, shared, or failover (default: shared)
- `--timeout`: Time in seconds to consume messages (default: 60, 0 for indefinite)
- `--earliest`: Start consuming from earliest available message

## Examples

### Example 1: Basic Producer-Consumer Test

1. Start a consumer in one terminal:
```bash
kubectl exec -it -n pulsar pulsar-test-client -- python /app/scripts/pulsar_consumer.py --topic persistent://public/default/test-topic --earliest
```

2. In another terminal, run the producer:
```bash
kubectl exec -it -n pulsar pulsar-test-client -- python /app/scripts/pulsar_producer.py --topic persistent://public/default/test-topic --num-messages 5
```

### Example 2: High Volume Test

Send 100 messages in batch mode:
```bash
kubectl exec -it -n pulsar pulsar-test-client -- python /app/scripts/pulsar_producer.py --topic persistent://public/default/high-volume --num-messages 100 --batch
```

Consume with a longer timeout:
```bash
kubectl exec -it -n pulsar pulsar-test-client -- python /app/scripts/pulsar_consumer.py --topic persistent://public/default/high-volume --timeout 300
```

## Troubleshooting

- If the scripts fail to connect to Pulsar, verify the broker service is running:
  ```bash
  kubectl get services -n pulsar
  ```

- To check the logs of the test client pod:
  ```bash
  kubectl logs -n pulsar pulsar-test-client
  ```

- If needed, you can bash into the pod for debugging:
  ```bash
  kubectl exec -it -n pulsar pulsar-test-client -- /bin/bash
  ```