# Lab 4: Kubernetes Cloud Deployment

This project deploys our housing price prediction API to AWS EKS using Kubernetes and Kustomize. It extends the functionality of Lab 3 by enabling deployment to both a local Minikube environment and a production AWS environment.

## Overview

This application provides:
- A machine learning model for predicting California housing prices
- Redis caching for improved performance
- Kubernetes deployment configurations for both local and cloud environments
- Automated build, push, and deployment scripts

## Prerequisites

- Docker
- Kubernetes CLI (kubectl)
- Minikube (for local development)
- AWS CLI configured with appropriate credentials
- Access to the class AWS account

## Configuration Files Structure
.k8s/
├── base/                   # Base Kubernetes manifests
│   ├── deployment-lab4.yaml
│   ├── deployment-redis.yaml
│   ├── kustomization.yaml
│   ├── service-lab4.yaml
│   └── service-redis.yaml
└── overlays/
├── dev/                # Development environment (Minikube)
│   ├── kustomization.yaml
│   ├── namespace.yaml
│   └── service-lab4-lb.yaml
└── prod/               # Production environment (AWS EKS)
├── hpa-api.yaml
├── kustomization.yaml
└── virtual-service.yaml
Copy
## Building and Deploying

### Setting Up AWS Access

Before deploying to production, set up AWS access:

```bash
# Login to AWS SSO
aws sso login --profile ucberkeley-sso

# Authenticate to the EKS cluster
aws eks update-kubeconfig --name eks-datasci255-students --profile ucberkeley-student

# Login to ECR repository
aws ecr get-login-password --region us-west-2 --profile ucberkeley-student | docker login --username AWS --password-stdin 650251712107.dkr.ecr.us-west-2.amazonaws.com
Building and Pushing the Image
The build-push.sh script handles building the Docker image, tagging it with the git commit hash, and pushing it to ECR:
bashCopy./build-push.sh
This script:

Gets the current git commit hash for the tag
Builds the Docker image with the appropriate platform
Tags the image with the ECR repository path
Pushes the image to ECR
Updates the kustomization.yaml file with the new tag

Deploying to Development Environment (Minikube)
bashCopy./deploy.sh
This will:

Switch to the Minikube context
Set up Docker to use Minikube's Docker daemon
Build the Docker image locally
Apply the Kubernetes configurations for development
Start a Minikube tunnel for accessing the service

Deploying to Production Environment (AWS EKS)
bashCopy./deploy.sh prod
This will:

Switch to the EKS context
Apply the Kubernetes configurations for production
Create a Redis service alias (if needed) to ensure connectivity

Additional Setup (if Redis connection issues occur)
If you encounter Redis connection issues, create a Redis service alias:
bashCopykubectl apply -f - <<EOF
apiVersion: v1
kind: Service
metadata:
  name: redis
  namespace: gibbons-tony
spec:
  type: ExternalName
  externalName: redis-service.gibbons-tony.svc.cluster.local
EOF
Testing the Deployment
Development Environment
After deploying to Minikube:
bashCopy# Get the service URL
minikube service lab-prediction-service -n w255 --url

# Test health endpoint
curl <service-url>/lab/health

# Test prediction endpoint
curl -X POST <service-url>/lab/predict \
  -H "Content-Type: application/json" \
  -d '{"MedInc": 8.3252, "HouseAge": 42, "AveRooms": 6.98, "AveBedrms": 1.02, "Population": 322, "AveOccup": 2.55, "Latitude": 37.88, "Longitude": -122.23}'
Production Environment
After deploying to AWS EKS:
bashCopy# Test health endpoint
curl https://gibbons-tony.mids255.com/lab/health

# Test single prediction endpoint
curl -X POST https://gibbons-tony.mids255.com/lab/predict \
  -H "Content-Type: application/json" \
  -d '{"MedInc": 8.3252, "HouseAge": 42, "AveRooms": 6.98, "AveBedrms": 1.02, "Population": 322, "AveOccup": 2.55, "Latitude": 37.88, "Longitude": -122.23}'

# Test bulk prediction endpoint
curl -X POST https://gibbons-tony.mids255.com/lab/bulk-predict \
  -H "Content-Type: application/json" \
  -d '{"houses": [{"MedInc": 8.3252, "HouseAge": 42, "AveRooms": 6.98, "AveBedrms": 1.02, "Population": 322, "AveOccup": 2.55, "Latitude": 37.88, "Longitude": -122.23}]}'
Cleaning Up
Development Environment
bashCopy# Delete namespace and resources
kubectl delete namespace w255

# Stop Minikube
minikube stop
Production Environment
bashCopy# Delete your deployed resources
kubectl delete -k .k8s/overlays/prod
# Updated build
