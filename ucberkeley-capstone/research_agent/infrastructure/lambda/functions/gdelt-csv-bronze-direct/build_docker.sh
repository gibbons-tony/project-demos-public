#!/bin/bash

# Build Lambda deployment package using Docker for Amazon Linux compatibility

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

echo "============================================================"
echo "Building Lambda Package with Docker (Amazon Linux)"
echo "============================================================"
echo ""

# Build Docker image
echo "Step 1: Building Docker image..."
docker build -t gdelt-bronze-builder .

# Create container and copy assets
echo ""
echo "Step 2: Extracting built assets..."
CONTAINER_ID=$(docker create gdelt-bronze-builder)
rm -rf package
mkdir -p package
docker cp "$CONTAINER_ID":/asset/. package/
docker rm "$CONTAINER_ID"

# Create deployment zip
echo ""
echo "Step 3: Creating deployment.zip..."
cd package
zip -r ../deployment.zip . -q
cd ..

# Get size
FILE_SIZE=$(du -h deployment.zip | cut -f1)

echo ""
echo "============================================================"
echo "✓ Build Complete!"
echo "============================================================"
echo "Package: deployment.zip"
echo "Size:    $FILE_SIZE"
echo ""
echo "Next step: Run ./deploy.sh to deploy to AWS Lambda"
echo ""
