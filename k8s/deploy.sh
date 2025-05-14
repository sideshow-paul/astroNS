#!/bin/bash
set -e

# Define color codes
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Print header
echo -e "${GREEN}=== AstroNS Kubernetes Deployment Script ===${NC}"
echo -e "${YELLOW}This script will deploy AstroNS with Pulsar to your Kubernetes cluster${NC}"
echo ""

# Check kubectl availability
if ! command -v kubectl &> /dev/null; then
    echo -e "${RED}kubectl not found. Please install kubectl and try again.${NC}"
    exit 1
fi

# Check if we're connected to a Kubernetes cluster
if ! kubectl cluster-info &> /dev/null; then
    echo -e "${RED}Not connected to a Kubernetes cluster. Please check your kubeconfig.${NC}"
    exit 1
fi

# Check if the default StorageClass exists
if ! kubectl get storageclass standard &> /dev/null; then
    echo -e "${YELLOW}StorageClass 'standard' not found. Checking for any available StorageClass...${NC}"
    AVAILABLE_SC=$(kubectl get storageclass -o jsonpath='{.items[0].metadata.name}' 2>/dev/null)

    if [ -z "$AVAILABLE_SC" ]; then
        echo -e "${RED}No StorageClass found. Please create a StorageClass or modify the PVC in deployment.yaml.${NC}"
        exit 1
    else
        echo -e "${YELLOW}Using StorageClass '$AVAILABLE_SC' instead of 'standard'.${NC}"
        # Replace standard with available StorageClass in deployment.yaml
        sed -i.bak "s/storageClassName: standard/storageClassName: $AVAILABLE_SC/g" k8s/deployment.yaml
        if [ $? -ne 0 ]; then
            echo -e "${RED}Failed to modify deployment.yaml. Please update StorageClass manually.${NC}"
            exit 1
        fi
        rm -f k8s/deployment.yaml.bak
    fi
fi

# Check if image exists
if ! docker images | grep -q "astrons" &> /dev/null; then
    echo -e "${YELLOW}AstroNS Docker image not found. Building image...${NC}"
    if [ -f "Dockerfile" ]; then
        docker build -t astrons:latest .
        if [ $? -ne 0 ]; then
            echo -e "${RED}Failed to build Docker image. Please build it manually.${NC}"
            exit 1
        fi
    else
        echo -e "${RED}Dockerfile not found. Please build the image manually.${NC}"
        exit 1
    fi
fi

# Check if Pulsar namespace exists
if ! kubectl get namespace pulsar &> /dev/null; then
    echo -e "${YELLOW}Creating Pulsar namespace...${NC}"
    kubectl create namespace pulsar
    if [ $? -ne 0 ]; then
        echo -e "${RED}Failed to create Pulsar namespace. Please check your permissions.${NC}"
        exit 1
    fi
fi

# Apply Pulsar configuration
echo -e "${YELLOW}Applying Pulsar configuration...${NC}"
kubectl apply -f k8s/pulsar-config.yaml -n pulsar

# Deploy Pulsar
echo -e "${YELLOW}Deploying Pulsar broker...${NC}"
kubectl apply -f k8s/pulsar.yaml -n pulsar
if [ $? -ne 0 ]; then
    echo -e "${RED}Failed to deploy Pulsar. Please check your YAML files and permissions.${NC}"
    exit 1
fi

# Wait for Pulsar to be ready
echo -e "${YELLOW}Waiting for Pulsar to be ready (this may take a few minutes)...${NC}"
kubectl wait --for=condition=ready pod -l app=pulsar,component=broker -n pulsar --timeout=600s
if [ $? -ne 0 ]; then
    echo -e "${RED}Timed out waiting for Pulsar to be ready. Please check Pulsar pods:${NC}"
    kubectl get pods -n pulsar
    echo -e "${RED}Check logs with: kubectl logs -n pulsar -l app=pulsar,component=broker${NC}"
    exit 1
fi

# Create Pulsar topics
# echo -e "${YELLOW}Creating Pulsar topics...${NC}"
# if ! kubectl exec -n pulsar pulsar-broker-0 -- bin/pulsar-admin topics create-partitioned-topic -p 1 persistent://public/default/my-topic; then
#     echo -e "${YELLOW}Failed to create 'my-topic' - it may already exist${NC}"
#     kubectl exec -n pulsar pulsar-broker-0 -- bin/pulsar-admin topics list public/default | grep my-topic || {
#         echo -e "${RED}Topic 'my-topic' creation failed and it doesn't exist. Check Pulsar.${NC}"
#         exit 1
#     }
# fi

# if ! kubectl exec -n pulsar pulsar-broker-0 -- bin/pulsar-admin topics create-partitioned-topic -p 1 persistent://public/default/sim_output; then
#     echo -e "${YELLOW}Failed to create 'sim_output' - it may already exist${NC}"
#     kubectl exec -n pulsar pulsar-broker-0 -- bin/pulsar-admin topics list public/default | grep sim_output || {
#         echo -e "${RED}Topic 'sim_output' creation failed and it doesn't exist. Check Pulsar.${NC}"
#         exit 1
#     }
# fi

# Apply AstroNS configuration
echo -e "${YELLOW}Applying AstroNS configuration...${NC}"
kubectl apply -f k8s/configmap.yaml
if [ $? -ne 0 ]; then
    echo -e "${RED}Failed to apply AstroNS configuration. Please check your YAML files and permissions.${NC}"
    exit 1
fi

# Deploy AstroNS
echo -e "${YELLOW}Deploying AstroNS...${NC}"
kubectl apply -f k8s/deployment.yaml
if [ $? -ne 0 ]; then
    echo -e "${RED}Failed to deploy AstroNS. Please check your YAML files and permissions.${NC}"
    exit 1
fi

# Wait for AstroNS to be ready
echo -e "${YELLOW}Waiting for AstroNS to be ready...${NC}"
kubectl wait --for=condition=ready pod -l app=astrons --timeout=300s
if [ $? -ne 0 ]; then
    echo -e "${RED}Timed out waiting for AstroNS to be ready. Please check AstroNS pods:${NC}"
    kubectl get pods -l app=astrons
    echo -e "${RED}Check logs with: kubectl logs -l app=astrons${NC}"
    exit 1
fi

echo -e "${GREEN}Deployment completed successfully!${NC}"
echo -e "${YELLOW}To check the status of the deployment:${NC}"
echo "kubectl get pods -n pulsar"
echo "kubectl get pods"
echo "kubectl logs -l app=astrons"
