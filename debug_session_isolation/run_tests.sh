#!/bin/bash

# Debug Session Isolation - Test Runner
# This script helps reproduce and test the session isolation issue

echo "=== Session Isolation Debug Test Runner ==="
echo

# Check if Docker containers are running
echo "1. Checking Docker containers..."
if ! docker ps | grep -q "logikal-middleware"; then
    echo "❌ logikal-middleware container is not running"
    echo "Please start the containers with: docker-compose up -d"
    exit 1
fi

if ! docker ps | grep -q "logikal-db"; then
    echo "❌ logikal-db container is not running"
    echo "Please start the containers with: docker-compose up -d"
    exit 1
fi

echo "✅ Docker containers are running"
echo

# Check database connectivity
echo "2. Testing database connectivity..."
if docker exec logikal-db psql -U admin -d logikal_middleware -c "SELECT 1;" > /dev/null 2>&1; then
    echo "✅ Database connection successful"
else
    echo "❌ Database connection failed"
    exit 1
fi
echo

# Run the sync endpoint test
echo "3. Running sync endpoint test..."
echo "Triggering project sync..."
SYNC_RESULT=$(curl -s -X POST http://localhost:8001/api/v1/sync/projects)
echo "Sync result: $SYNC_RESULT"
echo

# Check database state
echo "4. Checking database state..."
PROJECT_COUNT=$(docker exec logikal-db psql -U admin -d logikal_middleware -t -c "SELECT COUNT(*) FROM projects;" 2>/dev/null | tr -d ' ')
echo "Projects in database: $PROJECT_COUNT"

if [ "$PROJECT_COUNT" -eq "0" ]; then
    echo "❌ ISSUE CONFIRMED: No projects in database despite successful sync"
else
    echo "✅ Projects found in database"
fi
echo

# Show recent logs
echo "5. Recent sync logs:"
docker logs logikal-middleware --tail 20 | grep -E "(Processing project|Successfully processed|TRANSACTION.*commit|TRANSACTION.*rollback)"
echo

# Run the standalone test script
echo "6. Running standalone test script..."
if [ -f "test_script.py" ]; then
    echo "Executing test_script.py..."
    python3 test_script.py
else
    echo "❌ test_script.py not found"
fi
echo

echo "=== Test Summary ==="
echo "If you see '❌ ISSUE CONFIRMED' above, the session isolation bug is present."
echo "Check the logs and test script output for detailed analysis."
echo
echo "Files in this directory:"
ls -la
echo
echo "Next steps:"
echo "1. Review the logs in sync_logs.txt"
echo "2. Run test_script.py to isolate the issue"
echo "3. Share this debug package with external service"
