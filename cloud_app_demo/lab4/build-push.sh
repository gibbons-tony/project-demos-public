#!/bin/bash
set -e

# Get email prefix
EMAIL_PREFIX="gibbons-tony"
IMAGE_NAME="lab"
ECR_DOMAIN="650251712107.dkr.ecr.us-west-2.amazonaws.com"
IMAGE_FQDN="${ECR_DOMAIN}/${EMAIL_PREFIX}/${IMAGE_NAME}"

# Get short git hash (compliant with lab requirements)
TAG=$(git rev-parse --short HEAD)
echo "Building with tag: $TAG"

# Login to ECR
echo "Logging in to ECR..."
aws ecr get-login-password --region us-west-2 --profile ucberkeley-student | docker login --username AWS --password-stdin ${ECR_DOMAIN}

# Use buildx to build and push directly to ECR
echo "Building and pushing with buildx..."
# Create a builder if it doesn't exist
docker buildx create --name mybuilder --driver docker-container --bootstrap --use || true

# Build and push in one step
docker buildx build --platform=linux/amd64 --push -t ${IMAGE_FQDN}:${TAG} .

# Update kustomization.yaml with new tag
echo "Updating kustomization.yaml with tag: $TAG"
export TAG
sed -i '' "s/newTag: \".*\"/newTag: \"${TAG}\"/" .k8s/overlays/prod/kustomization.yaml

echo "Build and push complete. Image: ${IMAGE_FQDN}:${TAG}"