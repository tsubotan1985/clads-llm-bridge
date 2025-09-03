#!/bin/bash

# CLADS LLM Bridge Startup Script
# This script provides easy deployment options for the CLADS LLM Bridge

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_header() {
    echo -e "${BLUE}================================${NC}"
    echo -e "${BLUE}  CLADS LLM Bridge Deployment${NC}"
    echo -e "${BLUE}================================${NC}"
}

# Check if Docker is installed
check_docker() {
    if ! command -v docker &> /dev/null; then
        print_error "Docker is not installed. Please install Docker first."
        exit 1
    fi
    
    if ! command -v docker-compose &> /dev/null; then
        print_error "Docker Compose is not installed. Please install Docker Compose first."
        exit 1
    fi
}

# Show usage information
show_usage() {
    echo "Usage: $0 [OPTION]"
    echo ""
    echo "Options:"
    echo "  dev         Start in development mode (default)"
    echo "  prod        Start in production mode"
    echo "  build       Build the Docker image"
    echo "  stop        Stop the application"
    echo "  restart     Restart the application"
    echo "  logs        Show application logs"
    echo "  status      Show application status"
    echo "  clean       Clean up containers and volumes"
    echo "  help        Show this help message"
    echo ""
    echo "Environment variables:"
    echo "  WEB_UI_PORT     Web UI port (default: 4322)"
    echo "  PROXY_PORT      Proxy server port (default: 4321)"
    echo "  LOG_LEVEL       Logging level (default: INFO)"
}

# Start in development mode
start_dev() {
    print_status "Starting CLADS LLM Bridge in development mode..."
    docker-compose up -d
    show_access_info
}

# Start in production mode
start_prod() {
    print_status "Starting CLADS LLM Bridge in production mode..."
    docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d
    show_access_info
}

# Build the Docker image
build_image() {
    print_status "Building CLADS LLM Bridge Docker image..."
    docker-compose build --no-cache
    print_status "Build completed successfully!"
}

# Stop the application
stop_app() {
    print_status "Stopping CLADS LLM Bridge..."
    docker-compose down
    print_status "Application stopped."
}

# Restart the application
restart_app() {
    print_status "Restarting CLADS LLM Bridge..."
    docker-compose restart
    show_access_info
}

# Show logs
show_logs() {
    print_status "Showing CLADS LLM Bridge logs..."
    docker-compose logs -f
}

# Show status
show_status() {
    print_status "CLADS LLM Bridge Status:"
    docker-compose ps
    echo ""
    print_status "Container Health:"
    docker inspect clads-llm-bridge --format='{{.State.Health.Status}}' 2>/dev/null || echo "Health check not available"
}

# Clean up
clean_up() {
    print_warning "This will remove all containers and volumes. Are you sure? (y/N)"
    read -r response
    if [[ "$response" =~ ^([yY][eE][sS]|[yY])$ ]]; then
        print_status "Cleaning up CLADS LLM Bridge..."
        docker-compose down -v
        docker system prune -f
        print_status "Cleanup completed."
    else
        print_status "Cleanup cancelled."
    fi
}

# Show access information
show_access_info() {
    WEB_PORT=${WEB_UI_PORT:-4322}
    PROXY_PORT_VAR=${PROXY_PORT:-4321}
    
    echo ""
    print_status "CLADS LLM Bridge is starting up..."
    print_status "Please wait for the health check to pass (up to 40 seconds)"
    echo ""
    echo -e "${GREEN}Access URLs:${NC}"
    echo -e "  Configuration UI: ${BLUE}http://localhost:${WEB_PORT}${NC}"
    echo -e "  LLM Proxy API:    ${BLUE}http://localhost:${PROXY_PORT_VAR}${NC}"
    echo ""
    echo -e "${GREEN}Default Credentials:${NC}"
    echo -e "  Password: ${YELLOW}Hakodate4${NC}"
    echo ""
    echo -e "${GREEN}Useful Commands:${NC}"
    echo -e "  View logs:        ${BLUE}$0 logs${NC}"
    echo -e "  Check status:     ${BLUE}$0 status${NC}"
    echo -e "  Stop application: ${BLUE}$0 stop${NC}"
}

# Main script logic
main() {
    print_header
    check_docker
    
    case "${1:-dev}" in
        "dev")
            start_dev
            ;;
        "prod")
            start_prod
            ;;
        "build")
            build_image
            ;;
        "stop")
            stop_app
            ;;
        "restart")
            restart_app
            ;;
        "logs")
            show_logs
            ;;
        "status")
            show_status
            ;;
        "clean")
            clean_up
            ;;
        "help"|"-h"|"--help")
            show_usage
            ;;
        *)
            print_error "Unknown option: $1"
            echo ""
            show_usage
            exit 1
            ;;
    esac
}

# Run the main function
main "$@"