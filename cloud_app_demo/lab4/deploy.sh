#!/bin/bash
set -e

# Get environment from args
ENV=${1:-dev}
EMAIL_PREFIX="gibbons-tony"

if [ "$ENV" == "prod" ]; then
  echo "Deploying to production (AWS EKS)..."
  
  # Switch to EKS context
  kubectl config use-context arn:aws:eks:us-west-2:650251712107:cluster/eks-datasci255-students
  
  # Apply kustomize config
  kubectl apply -k .k8s/overlays/prod
  
  echo "Deployment complete. Service available at: https://${EMAIL_PREFIX}.mids255.com/lab/"
  
else
  echo "Deploying to development (Minikube)..."
  
  # Switch to Minikube context
  kubectl config use-context minikube
  
  # Set Docker environment to use Minikube's Docker daemon
  eval $(minikube docker-env)
  
  # Build the Docker image for local use
  docker build -t lab4:latest .
  
  # Apply kustomize config
  kubectl apply -k .k8s/overlays/dev
  
  # Start minikube tunnel in background
  echo "Starting minikube tunnel..."
  minikube tunnel > /dev/null 2>&1 &
  TUNNEL_PID=$!
  echo "Tunnel PID: $TUNNEL_PID"
  
  kubectl wait --namespace=w255 \
    --for=condition=ready pod \
    --selector=app=lab-api \
    --timeout=90s
    
  # Keep tunnel running - user must manually kill it later
  echo "To stop the tunnel, run: kill $TUNNEL_PID"
fi
