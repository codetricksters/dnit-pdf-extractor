#!/bin/bash

# Export Docker image to tar file for distribution
# This script creates a portable Docker image that can be shared with others

set -e

IMAGE_NAME="dnit-pdf-extractor-dnit-pdf-extractor:latest"
OUTPUT_FILE="dnit-pdf-extractor.tar"

echo "🐋 Exporting Docker image: $IMAGE_NAME"
echo "📦 Output file: $OUTPUT_FILE"
echo ""

# Check if image exists
if ! docker image inspect $IMAGE_NAME >/dev/null 2>&1; then
    echo "❌ Error: Image '$IMAGE_NAME' not found!"
    echo "Please build the image first with: docker compose up -d --build"
    exit 1
fi

# Export the image
echo "⏳ Exporting image (this may take a few minutes)..."
docker save -o $OUTPUT_FILE $IMAGE_NAME

# Get file size
FILE_SIZE=$(du -h $OUTPUT_FILE | cut -f1)

echo ""
echo "✅ Export complete!"
echo "📊 File size: $FILE_SIZE"
echo ""
echo "📤 To share this image:"
echo "   1. Transfer the file '$OUTPUT_FILE' to the target machine"
echo "   2. On the target machine, run: docker load -i $OUTPUT_FILE"
echo "   3. Then run: docker run -d -p 8000:8000 --name dnit-pdf-extractor $IMAGE_NAME"
echo ""
echo "📖 See DOCKER_INSTRUCTIONS.md for complete installation guide"
