#!/bin/bash

# Logikal Development Environment Startup Script
# This script starts the Odoo development environment for Logikal API experimentation

echo "Starting Logikal Development Environment..."
echo "=========================================="

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "Error: Docker is not running. Please start Docker first."
    exit 1
fi

# Navigate to the project directory
cd "$(dirname "$0")"

# Stop any existing containers
echo "Stopping any existing containers..."
docker-compose down

# Start the containers
echo "Starting containers..."
docker-compose up -d

# Wait for containers to be ready
echo "Waiting for containers to be ready..."
sleep 10

# Check container status
echo "Container Status:"
docker-compose ps

echo ""
echo "=========================================="
echo "Logikal Development Environment is ready!"
echo "=========================================="
echo ""
echo "Access URLs:"
echo "  Odoo Web Interface: http://localhost:8071"
echo "  Database: localhost:5432 (if needed)"
echo ""
echo "Container Names:"
echo "  Odoo: odoo-logikal-dev"
echo "  Database: odoo-logikal-db"
echo ""
echo "Useful Commands:"
echo "  View logs: docker-compose logs -f"
echo "  Stop containers: docker-compose down"
echo "  Restart: docker-compose restart"
echo "  Shell access: docker exec -it odoo-logikal-dev bash"
echo ""
