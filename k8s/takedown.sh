#!/bin/bash
set -e

# Define color codes
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Print header
echo -e "${GREEN}=== AstroNS Kubernetes Takedown Script ===${NC}"
echo -e "${YELLOW}This script will remove AstroNS and Pulsar from your Kubernetes cluster${NC}"
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

# Remove AstroNS
echo -e "${YELLOW}Removing AstroNS deployment...${NC}"
if kubectl get deployment astrons &> /dev/null; then
    kubectl delete -f k8s/deployment.yaml
    if [ $? -ne 0 ]; then
        echo -e "${RED}Failed to remove AstroNS deployment. Attempting force removal...${NC}"
        kubectl delete deployment astrons --force --grace-period=0 || true
    fi
    echo -e "${GREEN}AstroNS deployment removed.${NC}"
else
    echo -e "${YELLOW}AstroNS deployment not found.${NC}"
fi

# Remove AstroNS configuration
echo -e "${YELLOW}Removing AstroNS configuration...${NC}"
if kubectl get configmap astrons-config &> /dev/null; then
    kubectl delete -f k8s/configmap.yaml
    if [ $? -ne 0 ]; then
        echo -e "${RED}Failed to remove ConfigMap with YAML. Attempting direct removal...${NC}"
        kubectl delete configmap astrons-config || true
    fi
    echo -e "${GREEN}AstroNS configuration removed.${NC}"
else
    echo -e "${YELLOW}AstroNS configuration not found.${NC}"
fi

# Remove PVC
echo -e "${YELLOW}Removing AstroNS PersistentVolumeClaim...${NC}"
if kubectl get pvc astrons-results-pvc &> /dev/null; then
    kubectl delete pvc astrons-results-pvc
    if [ $? -ne 0 ]; then
        echo -e "${RED}Failed to remove PVC. It might be in use. Attempting force removal...${NC}"
        kubectl delete pvc astrons-results-pvc --force --grace-period=0 || true
    fi
    echo -e "${GREEN}AstroNS PersistentVolumeClaim removed.${NC}"
else
    echo -e "${YELLOW}AstroNS PersistentVolumeClaim not found.${NC}"
fi

# # Remove Pulsar
# echo -e "${YELLOW}Removing Pulsar...${NC}"
# bash k8s/takedown_pulsar.sh
# if [ $? -ne 0 ]; then
#     echo -e "${RED}Failed to remove Pulsar. Please check the Pulsar takedown script.${NC}"
#     exit 1
# fi

# echo -e "${GREEN}Takedown completed!${NC}"
# echo -e "${YELLOW}To verify resources have been removed:${NC}"
# echo "kubectl get pods -n pulsar"
# echo "kubectl get pods"
# echo "kubectl get namespaces"
# echo "kubectl get pvc"
# echo -e "${YELLOW}If some resources are still terminating, you can check again later or use force delete flags.${NC}"
