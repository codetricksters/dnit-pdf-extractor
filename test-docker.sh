#!/bin/bash

# Quick test script to verify the Docker container is working

set -e

echo "🧪 Testing DNIT PDF Extractor Docker Container"
echo ""

# Check if container is running
echo "1️⃣  Checking if container is running..."
if docker ps | grep -q dnit-pdf-extractor; then
    echo "✅ Container is running"
else
    echo "❌ Container is not running!"
    echo "   Start it with: docker compose up -d"
    exit 1
fi

# Check if port is accessible
echo ""
echo "2️⃣  Checking if application responds..."
if curl -s -f http://localhost:8000/ > /dev/null; then
    echo "✅ Application is accessible at http://localhost:8000"
else
    echo "❌ Application is not responding!"
    echo "   Check logs with: docker compose logs"
    exit 1
fi

# Check logs for errors
echo ""
echo "3️⃣  Checking for errors in logs..."
ERROR_COUNT=$(docker compose logs --tail=50 2>&1 | grep -i "error\|exception\|failed" | grep -v "WARNING" | wc -l)
if [ "$ERROR_COUNT" -eq 0 ]; then
    echo "✅ No errors found in recent logs"
else
    echo "⚠️  Found $ERROR_COUNT potential errors in logs"
    echo "   View with: docker compose logs"
fi

# Test homepage
echo ""
echo "4️⃣  Testing homepage..."
if curl -s http://localhost:8000/ | grep -q "DNIT\|Upload\|PDF"; then
    echo "✅ Homepage content looks correct"
else
    echo "⚠️  Homepage content unexpected"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✨ All tests passed!"
echo ""
echo "📱 Open http://localhost:8000 to use the application"
echo "📊 Dashboard: http://localhost:8000/dash/"
echo "📝 Logs: docker compose logs -f"
echo "🛑 Stop: docker compose down"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
