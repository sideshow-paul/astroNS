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

# Deploy Pulsar Manager
echo -e "${YELLOW}Deploying Pulsar Manager...${NC}"
cat <<EOF | kubectl apply -f - -n pulsar
apiVersion: apps/v1
kind: Deployment
metadata:
  name: pulsar-manager
  labels:
    app: pulsar
    component: manager
spec:
  replicas: 1
  selector:
    matchLabels:
      app: pulsar
      component: manager
  template:
    metadata:
      labels:
        app: pulsar
        component: manager
    spec:
      containers:
      - name: pulsar-manager
        image: apachepulsar/pulsar-manager:v0.4.0
        ports:
        - containerPort: 9527
        env:
        - name: SPRING_CONFIGURATION_FILE
          value: /pulsar-manager/pulsar-manager/application.properties

EOF

# Create Pulsar Manager service
echo -e "${YELLOW}Creating Pulsar Manager service...${NC}"
cat <<EOF | kubectl apply -f - -n pulsar
apiVersion: v1
kind: Service
metadata:
  name: pulsar-manager
  labels:
    app: pulsar
    component: manager
spec:
  ports:
  - port: 9527
    name: pulsar-manager
    targetPort: 9527
  selector:
    app: pulsar
    component: manager
  type: NodePort
EOF

# Wait for Pulsar to be ready
echo -e "${YELLOW}Waiting for Pulsar to be ready (this may take a few minutes)...${NC}"
kubectl wait --for=condition=ready pod -l app=pulsar,component=broker -n pulsar --timeout=600s
if [ $? -ne 0 ]; then
    echo -e "${RED}Timed out waiting for Pulsar to be ready. Please check Pulsar pods:${NC}"
    kubectl get pods -n pulsar
    echo -e "${RED}Check logs with: kubectl logs -n pulsar -l app=pulsar,component=broker${NC}"
    exit 1
fi

# Wait for Pulsar Manager to be ready
echo -e "${YELLOW}Waiting for Pulsar Manager to be ready...${NC}"
kubectl wait --for=condition=ready pod -l app=pulsar,component=manager -n pulsar --timeout=300s
if [ $? -ne 0 ]; then
    echo -e "${RED}Timed out waiting for Pulsar Manager to be ready. Please check Pulsar Manager pods:${NC}"
    kubectl get pods -n pulsar -l app=pulsar,component=manager
    echo -e "${RED}Check logs with: kubectl logs -n pulsar -l app=pulsar,component=manager${NC}"
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

# Display Pulsar Manager access information
PULSAR_MANAGER_PORT=$(kubectl get svc pulsar-manager -n pulsar -o jsonpath='{.spec.ports[0].nodePort}')
if [ -n "$PULSAR_MANAGER_PORT" ]; then
    echo -e "${GREEN}Pulsar Manager UI is available at:${NC}"
    echo -e "http://<your-node-ip>:$PULSAR_MANAGER_PORT"
    echo -e "${YELLOW}Setting up initial admin user...${NC}"

    # Wait for the Pulsar Manager API to be ready
    echo -e "${YELLOW}Waiting for Pulsar Manager API to be ready...${NC}"
    kubectl wait --for=condition=ready pod -l app=pulsar,component=manager -n pulsar --timeout=180s

    # Create the initial admin user using CSRF token approach
    echo -e "${YELLOW}Creating admin user for Pulsar Manager...${NC}"

    # Wait a bit for the service to be fully ready
    sleep 10

    # Get CSRF token and create admin user
    echo -e "${YELLOW}Getting CSRF token and creating admin user...${NC}"
    CSRF_TOKEN=$(curl http://localhost:$PULSAR_MANAGER_PORT/pulsar-manager/csrf-token)
    echo $CSRF_TOKEN
    sleep 10
    # Create the admin user with CSRF token
    echo -e "${YELLOW}Creating admin user with CSRF token...${NC}"
    curl \
      -H 'X-XSRF-TOKEN: $CSRF_TOKEN' \
      -H 'Cookie: XSRF-TOKEN=$CSRF_TOKEN;' \
      -H "Content-Type: application/json" \
      -X PUT http://localhost:$PULSAR_MANAGER_PORT/pulsar-manager/users/superuser \
      -d '{"name": "admin", "password": "apachepulsar", "description": "Administrator", "email": "admin@example.org"}'

    echo ""

    echo -e "${GREEN}Pulsar Manager initial setup complete${NC}"
    echo -e "${YELLOW}Access the Pulsar Manager UI at http://<your-node-ip>:$PULSAR_MANAGER_PORT${NC}"
    echo -e "${YELLOW}Log in with:${NC}"
    echo -e "  Username: admin"
    echo -e "  Password: apachepulsar"
    echo -e "${YELLOW}After logging in, add a new environment with these settings:${NC}"
    echo -e "  Name: pulsar-local"
    echo -e "  Service URL: http://pulsar-broker:8080"
    echo -e "  Broker URL for WebSocket: ws://pulsar-broker:8080"
fi
