#!/bin/bash

# Function to check if a command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Check for required commands
if ! command_exists docker; then
    echo "Error: docker is not installed"
    exit 1
fi

if ! command_exists docker-compose; then
    echo "Error: docker-compose is not installed"
    exit 1
fi

# Create necessary directories
mkdir -p data/query_results

# Copy test environment file if it doesn't exist
if [ ! -f .env ]; then
    if [ -f .env.test ]; then
        cp .env.test .env
        echo "Created .env from .env.test"
    else
        echo "Error: .env.test file not found"
        exit 1
    fi
fi

# Function to check if containers are healthy
check_health() {
    local retries=30
    local wait_time=2
    
    echo "Checking service health..."
    
    while [ $retries -gt 0 ]; do
        if docker-compose ps | grep -q "unhealthy\|exit"; then
            echo "Error: Some containers are unhealthy or have exited"
            docker-compose logs
            exit 1
        fi
        
        # Check if all services are running
        local running_count=$(docker-compose ps | grep -c "Up")
        if [ "$running_count" -eq 5 ]; then
            echo "All services are up and running!"
            return 0
        fi
        
        echo "Waiting for services to be ready... ($retries attempts left)"
        sleep $wait_time
        retries=$((retries-1))
    done
    
    echo "Error: Services did not become healthy in time"
    docker-compose logs
    exit 1
}

# Clean up function
cleanup() {
    echo "Cleaning up..."
    docker-compose down -v
}

# Set up trap for cleanup
trap cleanup EXIT INT TERM

# Start services
echo "Starting services..."
docker-compose up --build -d

# Check health
check_health

# Show endpoints
echo "
Services are ready:
- FastAPI: http://localhost:8000
- FastAPI Docs: http://localhost:8000/docs
- Flower: http://localhost:5555

Test admin credentials:
- Username: admin
- Password: admin_test_password

Press Ctrl+C to stop services
"

# Keep script running
tail -f /dev/null 