# Docker and Kubernetes Deployment for astroNS

This guide provides instructions for building a Docker image of the astroNS project and deploying it to a Kubernetes cluster with Apache Pulsar for messaging.

## Prerequisites

- Docker installed
- Kubernetes cluster configured (minikube, kind, or cloud provider)
- kubectl installed and configured
- Helm (optional, for Pulsar deployment via charts)

## Building the Docker Image

From the root directory of the astroNS project, build the Docker image:

```bash
docker build -t astrons:latest .
```

If you're using a container registry, tag and push the image:

```bash
docker tag astrons:latest your-registry/astrons:latest
docker push your-registry/astrons:latest
```

## Deploying to Kubernetes

### 1. Update Image Reference (if using a registry)

Edit `k8s/deployment.yaml` and replace:

```yaml
image: astrons:latest
```

with

```yaml
image: your-registry/astrons:latest
```

### 2. Deploy Apache Pulsar

First, create the Pulsar namespace:

```bash
kubectl apply -f k8s/pulsar.yaml
```

Wait for the Pulsar broker to be ready:

```bash
kubectl wait --for=condition=ready pod -l app=pulsar,component=broker -n pulsar --timeout=300s
```

### 3. Create the Kubernetes Resources for astroNS

Apply the ConfigMap first:

```bash
kubectl apply -f k8s/configmap.yaml
```

Then deploy the application:

```bash
kubectl apply -f k8s/deployment.yaml
```

### 4. Verify Deployment

Check if the pod is running:

```bash
kubectl get pods -l app=astrons
```

View pod logs:

```bash
kubectl logs -l app=astrons
```

Check Pulsar service:

```bash
kubectl get pods -n pulsar
kubectl logs -l app=pulsar,component=broker -n pulsar
```

### 4. Accessing Results

The simulation results are stored in the persistent volume. To access them, you can:

- Create a pod that mounts the same PVC and copy files from there
- Set up a data transfer job to copy results to another location

Example to copy results:

```bash
kubectl cp <pod-name>:/app/Results ./local-results
```

## Customizing the Deployment

### Modifying Configuration

Edit the `k8s/configmap.yaml` file to change simulation parameters.

### Scaling

To run multiple simulations, increase the number of replicas:

```bash
kubectl scale deployment astrons --replicas=3
```

### Resource Adjustments

Modify CPU and memory requests/limits in `k8s/deployment.yaml` according to your simulation needs.

## Troubleshooting

### Pod Fails to Start

Check events:

```bash
kubectl describe pod <pod-name>
```

### Resource Issues

If pods are evicted or OOM killed, increase the resource limits in the deployment file.

### ConfigMap Updates

After updating the ConfigMap, you need to restart the pods:

```bash
kubectl rollout restart deployment astrons
```

### Pulsar Connectivity Issues

If the astroNS application cannot connect to Pulsar:

1. Verify Pulsar is running:
   ```bash
   kubectl get pods -n pulsar
   ```

2. Check Pulsar logs:
   ```bash
   kubectl logs -l app=pulsar,component=broker -n pulsar
   ```

3. Check network connectivity:
   ```bash
   kubectl exec -it <astrons-pod-name> -- nc -zv pulsar-broker.pulsar.svc.cluster.local 6650
   ```

4. Verify the Pulsar connection URL in `SimpleSensorCollectionModel.yml`

## Advanced: Using Kubernetes Jobs

For one-time simulations, consider using Kubernetes Jobs instead of Deployments. Create a `job.yaml` file based on the deployment template with appropriate modifications.

## Pulsar Management

### Accessing the Pulsar Admin UI

The Pulsar Admin UI is available at port 8080. To access it:

```bash
# Port forward the Pulsar Admin UI
kubectl port-forward -n pulsar svc/pulsar-broker 8080:8080
```

Then access http://localhost:8080 in your browser.

### Creating Topics

To create topics in Pulsar:

```bash
# Enter the Pulsar pod
kubectl exec -it -n pulsar statefulset/pulsar-broker -- /bin/bash

# Create a topic
./bin/pulsar-admin topics create persistent://public/default/my-topic
./bin/pulsar-admin topics create persistent://public/default/sim_output
```

### Viewing Topic Activity

```bash
# View topics
./bin/pulsar-admin topics list public/default

# View producers
./bin/pulsar-admin topics stats persistent://public/default/my-topic
```