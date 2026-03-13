
# Machine Learning Sentiment Analysis API
This project deploys a sentiment analysis API to AWS EKS using a DistilBERT model that analyzes the sentiment of text inputs. The system is built with FastAPI, uses Redis for caching, and runs in Kubernetes both locally and in the AWS cloud.
## Overview
This application provides:

* Sentiment analysis using a pre-trained DistilBERT model
* Redis caching for improved performance and response time
* Kubernetes deployment configurations for both local and cloud environments
* Support for batch prediction requests

## Prerequisites

* Docker
* Kubernetes CLI (kubectl)
* Minikube (for local development)
* AWS CLI configured with appropriate credentials
* Access to the class AWS account


## Configuration Files Structure
.k8s/
├── base/                   # Base Kubernetes manifests
│   ├── deployment-mlapi.yaml
│   ├── deployment-redis.yaml
│   ├── kustomization.yaml
│   ├── service-mlapi.yaml
│   └── service-redis.yaml
└── overlays/
    ├── dev/                # Development environment (Minikube)
    │   ├── kustomization.yaml
    │   ├── namespace.yaml
    │   └── service-mlapi-lb.yaml
    └── prod/               # Production environment (AWS EKS)
        ├── hpa-mlapi.yaml
        ├── kustomization.yaml
        └── virtual-service.yaml

## Building and Deploying
### Setting Up AWS Access
Before deploying to production, set up AWS access:

aws sso login --profile ucberkeley-sso
aws eks update-kubeconfig --name eks-datasci255-students --profile ucberkeley-student
aws ecr get-login-password --region us-west-2 --profile ucberkeley-student | docker login --username AWS --password-stdin 650251712107.dkr.ecr.us-west-2.amazonaws.com

# Authenticate to the EKS cluster
aws eks update-kubeconfig --name eks-datasci255-students --profile ucberkeley-student

# Login to ECR repository
aws ecr get-login-password --region us-west-2 --profile ucberkeley-student | docker login --username AWS --password-stdin 650251712107.dkr.ecr.us-west-2.amazonaws.com
Building and Pushing the Image
The build-push.sh script handles building the Docker image, tagging it with the git commit hash, and pushing it to ECR:
bash./build-push.sh
This script:

Gets the current git commit hash for the tag
Builds the Docker image with the appropriate platform
Tags the image with the ECR repository path
Pushes the image to ECR
Updates the kustomization.yaml file with the new tag

Deploying to Development Environment (Minikube)
bash./deploy.sh
This will:

Switch to the Minikube context
Set up Docker to use Minikube's Docker daemon
Build the Docker image locally
Apply the Kubernetes configurations for development
Start a Minikube tunnel for accessing the service

Deploying to Production Environment (AWS EKS)
bash./deploy.sh prod
This will:

Switch to the EKS context
Apply the Kubernetes configurations for production

Testing the Deployment
Development Environment
After deploying to Minikube:
bash# Get the service URL
minikube service mlapi-service -n w255 --url

# Test health endpoint
curl <service-url>/project/health

# Test prediction endpoint
curl -X POST <service-url>/project/predict \
  -H "Content-Type: application/json" \
  -d '{"text": ["This is great!"]}'

# Test bulk-predict endpoint
curl -X POST <service-url>/project/bulk-predict \
  -H "Content-Type: application/json" \
  -d '{"text": ["This is great!", "This is terrible!"]}'
Production Environment
After deploying to AWS EKS:
bash# Test health endpoint
curl https://gibbons-tony.mids255.com/project/health

# Test prediction endpoint
curl -X POST https://gibbons-tony.mids255.com/project/predict \
  -H "Content-Type: application/json" \
  -d '{"text": ["This is great!"]}'

# Test bulk-predict endpoint
curl -X POST https://gibbons-tony.mids255.com/project/bulk-predict \
  -H "Content-Type: application/json" \
  -d '{"text": ["This is great!", "This is terrible!"]}'
Load Testing
To load test the API:
bash# Set your namespace
export NAMESPACE=gibbons-tony

# Run the k6 load test
k6 run -e NAMESPACE=${NAMESPACE} --summary-trend-stats "min,avg,med,max,p(90),p(95),p(99),p(99.99)" load.js
Monitor performance metrics in Grafana by setting up port-forwarding:
bashkubectl port-forward -n prometheus svc/grafana 3000:3000
Then access the Grafana dashboard at http://localhost:3000
Cleaning Up
Development Environment
bash# Delete namespace and resources
kubectl delete namespace w255

# Stop Minikube
minikube stop
Production Environment
bash# Delete your deployed resources
kubectl delete -k .k8s/overlays/prodRetryClaude does not have internet access. Links provided may not be accurate or up to date.Claude can make mistakes. Please double-check responses. 3.7 Sonnet

delete later.
