#!/bin/bash
set -e

# Define color codes
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Print header
echo -e "${GREEN}=== Pulsar Kubernetes Deployment Script ===${NC}"
echo -e "${YELLOW}This script will deploy Pulsar to your Kubernetes cluster${NC}"
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

# Check if Pulsar namespace exists
if ! kubectl get namespace pulsar &> /dev/null; then
    echo -e "${YELLOW}Creating Pulsar namespace...${NC}"
    kubectl create namespace pulsar
    if [ $? -ne 0 ]; then
        echo -e "${RED}Failed to create Pulsar namespace. Please check your permissions.${NC}"
        exit 1
    fi
fi

# Determine the correct path for YAML files
if [ -f "pulsar-config.yaml" ]; then
    CONFIG_PATH="pulsar-config.yaml"
    PULSAR_PATH="pulsar.yaml"
elif [ -f "k8s/pulsar-config.yaml" ]; then
    CONFIG_PATH="k8s/pulsar-config.yaml"
    PULSAR_PATH="k8s/pulsar.yaml"
else
    echo -e "${RED}Cannot find pulsar-config.yaml. Please run from project root or k8s directory.${NC}"
    exit 1
fi

# Apply Pulsar configuration
echo -e "${YELLOW}Applying Pulsar configuration...${NC}"
kubectl apply -f $CONFIG_PATH -n pulsar

# Deploy Pulsar
echo -e "${YELLOW}Deploying Pulsar broker...${NC}"
kubectl apply -f $PULSAR_PATH -n pulsar
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
          name: frontend
        - containerPort: 7750
          name: backend
        env:
        - name: SPRING_CONFIGURATION_FILE
          value: /pulsar-manager/pulsar-manager/application.properties
        - name: REDIRECT_HOST
          value: "0.0.0.0"
        - name: REDIRECT_PORT
          value: "9527"

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
    name: frontend
    targetPort: 9527
    nodePort: 30527
  - port: 7750
    name: backend
    targetPort: 7750
  selector:
    app: pulsar
    component: manager
  type: NodePort
EOF

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

echo -e "${GREEN}Pulsar deployment completed successfully!${NC}"
echo -e "${YELLOW}To check the status of Pulsar:${NC}"
echo "kubectl get pods -n pulsar"
echo "kubectl logs -n pulsar -l app=pulsar,component=broker"

# Display Pulsar Manager access information
PULSAR_MANAGER_UI_PORT=$(kubectl get svc pulsar-manager -n pulsar -o jsonpath='{.spec.ports[?(@.name=="frontend")].nodePort}')
PULSAR_MANAGER_API_PORT=$(kubectl get svc pulsar-manager -n pulsar -o jsonpath='{.spec.ports[?(@.name=="backend")].nodePort}')
#NODE_IP=$(kubectl get nodes -o jsonpath='{.items[0].status.addresses[?(@.type=="InternalIP")].address}')
NODE_IP=127.0.0.1

if [ -n "$PULSAR_MANAGER_UI_PORT" ]; then
    echo -e "${GREEN}Pulsar Manager UI is available at:${NC}"
    echo -e "http://$NODE_IP:$PULSAR_MANAGER_UI_PORT"
    echo -e "${YELLOW}Setting up initial admin user...${NC}"

    # Wait for the Pulsar Manager API to be ready
    echo -e "${YELLOW}Waiting for Pulsar Manager API to be ready...${NC}"
    kubectl wait --for=condition=ready pod -l app=pulsar,component=manager -n pulsar --timeout=180s

    # Create the initial admin user using CSRF token approach
    echo -e "${YELLOW}Creating admin user for Pulsar Manager...${NC}"

    # Wait a bit for the service to be fully ready
    sleep 6

    # Get CSRF token and create admin user
    echo -e "${YELLOW}Getting CSRF token and creating admin user...${NC}"
    CSRF_TOKEN=$(curl -s "http://127.0.0.1:30527/pulsar-manager/csrf-token")
    echo "CSRF Token: $CSRF_TOKEN"

    if [ -z "$CSRF_TOKEN" ]; then
        echo -e "${YELLOW}Could not retrieve CSRF token, trying again...${NC}"
        sleep 10
        CSRF_TOKEN=$(curl -s http://127.0.0.1:30527/pulsar-manager/csrf-token)
        echo "CSRF Token: $CSRF_TOKEN"
    fi

    # Create the admin user with CSRF token
    echo -e "${YELLOW}Creating admin user with CSRF token...${NC}"
    curl -s \
      -H "X-XSRF-TOKEN: $CSRF_TOKEN" \
      -H "Cookie: XSRF-TOKEN=$CSRF_TOKEN;" \
      -H "Content-Type: application/json" \
      -X PUT http://127.0.0.1:30527/pulsar-manager/users/superuser \
      -d '{"name": "admin", "password": "apachepulsar", "description": "Administrator", "email": "admin@example.org"}'

    echo ""

    echo -e "${GREEN}Pulsar Manager initial setup complete${NC}"
    echo -e "${YELLOW}Access the Pulsar Manager UI at http://$NODE_IP:$PULSAR_MANAGER_UI_PORT${NC}"
    echo -e "${YELLOW}Log in with:${NC}"
    echo -e "  Username: admin"
    echo -e "  Password: apachepulsar"
    echo -e "${YELLOW}After logging in, add a new environment with these settings:${NC}"
    echo -e "  Name: pulsar-local"
    echo -e "  Service URL: http://pulsar-broker:8080"
    echo -e "  Broker URL for WebSocket: ws://pulsar-broker:8080"
fi
