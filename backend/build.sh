#!/bin/bash
set -e

# Configuration
IMAGE_NAME="x1mvp/portfolio"
REGISTRY="ghcr.io"
VERSION=${1:-latest}
PLATFORM="linux/amd64,linux/arm64"

echo "🚀 Building x1mvp Portfolio Docker Image"
echo "📦 Image: $IMAGE_NAME:$VERSION"
echo "🏗️ Platform: $PLATFORM"

# Set build arguments
BUILD_DATE=$(date -u +'%Y-%m-%dT%H:%M:%SZ')
VCS_REF=$(git rev-parse --short HEAD)
COMMIT_HASH=$(git rev-parse HEAD)

echo "📅 Build Date: $BUILD_DATE"
echo "🔧 VCS Ref: $VCS_REF"

# Build multi-platform image
docker buildx build \
    --platform $PLATFORM \
    --tag $REGISTRY/$IMAGE_NAME:$VERSION \
    --tag $REGISTRY/$IMAGE_NAME:latest \
    --target production \
    --build-arg BUILD_DATE="$BUILD_DATE" \
    --build-arg VERSION="$VERSION" \
    --build-arg VCS_REF="$VCS_REF" \
    --build-arg COMMIT_HASH="$COMMIT_HASH" \
    --push \
    .

echo "✅ Build completed successfully!"
echo "🎯 Image: $REGISTRY/$IMAGE_NAME:$VERSION"

# Run security scan
echo "🔒 Running security scan..."
docker run --rm -v /var/run/docker.sock:/var/run/docker.sock \
    -v $PWD:/tmp/.cache/ aquasec/trivy:latest image \
    --exit-code 0 --no-progress --format table \
    $REGISTRY/$IMAGE_NAME:$VERSION

echo "🚀 Ready for deployment!"
