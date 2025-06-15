# Docker and Kubernetes Deployment for astroNS

This guide provides instructions for building a Docker image of the astroNS project and deploying it to a Kubernetes cluster with Apache Pulsar for messaging.

## Prerequisites

- Docker installed
- Kubernetes cluster configured (minikube, kind, or cloud provider)
- kubectl installed and configured
- curl (for Pulsar Manager setup)

## Deployment Scripts

This directory contains several deployment scripts for different use cases:

### Main Deployment Scripts

- **`deploy.sh`** - Main deployment script that deploys both Pulsar and AstroNS
- **`takedown.sh`** - Main takedown script that removes both AstroNS and Pulsar

### Pulsar-Only Scripts

- **`deploy_pulsar.sh`** - Deploy only Apache Pulsar with Pulsar Manager
- **`takedown_pulsar.sh`** - Remove only Apache Pulsar and related components

## Quick Start

### Deploy Everything (Recommended)

To deploy the complete stack (Pulsar + AstroNS):

```bash
# From the project root directory
./k8s/deploy.sh
```

This script will:
1. Check prerequisites (kubectl, Docker)
2. Build the AstroNS Docker image if needed
3. Deploy Apache Pulsar with Pulsar Manager
4. Deploy AstroNS application
5. Set up Pulsar Manager with admin user

### Deploy Only Pulsar

If you only want to deploy Pulsar:

```bash
# From the project root directory
./k8s/deploy_pulsar.sh

# Or from the k8s directory
cd k8s && ./deploy_pulsar.sh
```

### Remove Everything

To remove all deployed resources:

```bash
# From the project root directory
./k8s/takedown.sh
```

### Remove Only Pulsar

To remove only Pulsar while keeping AstroNS:

```bash
# From the project root directory
./k8s/takedown_pulsar.sh

# Or from the k8s directory
cd k8s && ./takedown_pulsar.sh
```

## Building the Docker Image

The deployment script will automatically build the Docker image if it doesn't exist. To build manually:

```bash
docker build -t astrons:latest .
```

If you're using a container registry, tag and push the image:

```bash
docker tag astrons:latest your-registry/astrons:latest
docker push your-registry/astrons:latest
```

Then update `k8s/deployment.yaml` to use your registry image.

## Accessing Services

### Pulsar Manager UI

After deployment, the script will display the Pulsar Manager access information:

```
Pulsar Manager UI is available at: http://<NODE_IP>:30527
Username: admin
Password: apachepulsar
```

To add the Pulsar environment in the UI:
- Name: pulsar-local
- Service URL: http://pulsar-broker:8080
- Broker URL for WebSocket: ws://pulsar-broker:8080

### Monitoring Deployments

Check the status of your deployments:

```bash
# Check AstroNS pods
kubectl get pods -l app=astrons

# Check Pulsar pods
kubectl get pods -n pulsar

# View AstroNS logs
kubectl logs -l app=astrons

# View Pulsar broker logs
kubectl logs -n pulsar -l app=pulsar,component=broker
```

## Manual Deployment (Alternative)

If you prefer to deploy manually without the scripts:

### 1. Deploy Apache Pulsar

```bash
kubectl create namespace pulsar
kubectl apply -f k8s/pulsar-config.yaml -n pulsar
kubectl apply -f k8s/pulsar.yaml -n pulsar
```

Wait for Pulsar to be ready:

```bash
kubectl wait --for=condition=ready pod -l app=pulsar,component=broker -n pulsar --timeout=600s
```

### 2. Deploy AstroNS

```bash
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/deployment.yaml
```

Wait for AstroNS to be ready:

```bash
kubectl wait --for=condition=ready pod -l app=astrons --timeout=300s
```

## Customizing the Deployment

### Modifying Configuration

Edit the `k8s/configmap.yaml` file to change simulation parameters.

### Scaling

To run multiple simulations:

```bash
kubectl scale deployment astrons --replicas=3
```

### Resource Adjustments

Modify CPU and memory requests/limits in `k8s/deployment.yaml` according to your simulation needs.

### Storage Class

The scripts automatically detect and use available StorageClasses. If you need a specific one, edit `k8s/deployment.yaml`.

## Accessing Results

The simulation results are stored in the persistent volume. To access them:

```bash
# Copy results from pod to local machine
kubectl cp <pod-name>:/app/Results ./local-results

# Or exec into the pod
kubectl exec -it <pod-name> -- /bin/bash
```

## Troubleshooting

### Deployment Issues

If deployment fails:

1. Check cluster connectivity:
   ```bash
   kubectl cluster-info
   ```

2. Check available storage classes:
   ```bash
   kubectl get storageclass
   ```

3. View pod events:
   ```bash
   kubectl describe pod <pod-name>
   ```

### Pulsar Connectivity Issues

If AstroNS cannot connect to Pulsar:

1. Verify Pulsar is running:
   ```bash
   kubectl get pods -n pulsar
   ```

2. Check Pulsar logs:
   ```bash
   kubectl logs -n pulsar -l app=pulsar,component=broker
   ```

3. Test connectivity:
   ```bash
   kubectl exec -it <astrons-pod-name> -- nc -zv pulsar-broker.pulsar.svc.cluster.local 6650
   ```

### Script Permissions

If you get permission errors, make the scripts executable:

```bash
chmod +x k8s/*.sh
```

### Resource Constraints

If pods are evicted or OOM killed:

1. Increase resource limits in `k8s/deployment.yaml`
2. Check cluster resource availability:
   ```bash
   kubectl top nodes
   kubectl describe nodes
   ```

## Pulsar Management

### Creating Topics Manually

```bash
# Access Pulsar admin
kubectl exec -it -n pulsar pulsar-broker-0 -- /bin/bash

# Create topics
./bin/pulsar-admin topics create-partitioned-topic -p 1 persistent://public/default/my-topic
./bin/pulsar-admin topics create-partitioned-topic -p 1 persistent://public/default/sim_output
```

### Viewing Topic Activity

```bash
# List topics
./bin/pulsar-admin topics list public/default

# View topic stats
./bin/pulsar-admin topics stats persistent://public/default/my-topic
```

## Advanced Usage

### Running as Kubernetes Jobs

For one-time simulations, consider using Kubernetes Jobs. Create a job configuration based on the deployment template.

### Multi-Environment Setup

You can deploy to different namespaces for multiple environments:

```bash
# Deploy to staging namespace
kubectl create namespace staging
kubectl apply -f k8s/configmap.yaml -n staging
kubectl apply -f k8s/deployment.yaml -n staging
```

### Backup and Recovery

To backup your configuration:

```bash
kubectl get configmap astrons-config -o yaml > backup-config.yaml
```