# CLADS LLM Bridge Integration Tests

This directory contains comprehensive integration tests for the CLADS LLM Bridge system. These tests verify the complete functionality from configuration through proxy operations to monitoring.

## Test Structure

### Integration Test Files

1. **`test_integration_config_workflow.py`**
   - Tests complete configuration workflow from authentication to service setup
   - Covers login, password changes, service configuration, model loading, and health checks
   - Verifies configuration persistence and error handling

2. **`test_integration_proxy_functionality.py`**
   - Tests proxy functionality with mock LLM services
   - Covers request routing, response transformation, and usage logging
   - Tests multiple service types including VS Code LM Proxy special handling

3. **`test_integration_monitoring_accuracy.py`**
   - Tests usage tracking and monitoring dashboard accuracy
   - Verifies correct calculation of statistics, leaderboards, and time-based filtering
   - Tests real-time updates and data consistency

4. **`test_integration_docker_deployment.py`**
   - Tests Docker container deployment and port accessibility
   - Verifies container startup, port binding, data persistence, and resource usage
   - Tests Docker Compose deployment and multiple container instances

### Supporting Files

- **`conftest.py`** - Pytest configuration and shared fixtures
- **`run_integration_tests.py`** - Test runner script with comprehensive reporting
- **`README.md`** - This documentation file

## Running Tests

### Prerequisites

1. **Python Dependencies**
   ```bash
   pip install pytest requests
   ```

2. **Docker** (for Docker tests)
   ```bash
   docker --version
   ```

3. **Project Setup**
   - Ensure you're in the `clads-llm-bridge` directory
   - All source code should be properly installed/available

### Running All Tests

```bash
# Run all integration tests
python tests/run_integration_tests.py

# Run with verbose output
python tests/run_integration_tests.py --verbose

# Skip Docker tests (if Docker not available)
python tests/run_integration_tests.py --skip-docker
```

### Running Specific Test Categories

```bash
# Run only configuration tests
python tests/run_integration_tests.py --test config

# Run only proxy tests
python tests/run_integration_tests.py --test proxy

# Run only monitoring tests
python tests/run_integration_tests.py --test monitoring

# Run only Docker tests
python tests/run_integration_tests.py --test docker
```

### Using pytest Directly

```bash
# Run all integration tests
pytest tests/test_integration_*.py -v

# Run specific test file
pytest tests/test_integration_config_workflow.py -v

# Run with markers
pytest -m "integration and not docker" -v

# Run with coverage
pytest tests/test_integration_*.py --cov=src --cov-report=html
```

## Test Categories and Markers

Tests are automatically marked with the following pytest markers:

- `@pytest.mark.integration` - All integration tests
- `@pytest.mark.docker` - Tests requiring Docker
- `@pytest.mark.slow` - Long-running tests
- `@pytest.mark.config` - Configuration-related tests
- `@pytest.mark.proxy` - Proxy functionality tests
- `@pytest.mark.monitoring` - Monitoring and usage tracking tests
- `@pytest.mark.auth` - Authentication tests

### Running by Markers

```bash
# Run only integration tests (exclude unit tests)
pytest -m integration

# Run all except Docker tests
pytest -m "integration and not docker"

# Run only slow tests
pytest -m slow

# Run only fast tests
pytest -m "not slow"
```

## Test Coverage

### Configuration Workflow Tests
- ✅ Authentication flow (login, password change)
- ✅ Service configuration (all supported service types)
- ✅ Model loading and discovery
- ✅ Health check functionality
- ✅ Configuration persistence
- ✅ Error handling and validation
- ✅ Multiple service configuration
- ✅ Session management

### Proxy Functionality Tests
- ✅ OpenAI service proxy integration
- ✅ Anthropic service proxy integration
- ✅ VS Code LM Proxy special handling
- ✅ Multiple service routing
- ✅ Response transformation with public names
- ✅ Usage logging integration
- ✅ Error handling and service unavailability
- ✅ Concurrent request handling
- ✅ LiteLLM configuration integration

### Monitoring Accuracy Tests
- ✅ Usage logging accuracy
- ✅ Client leaderboard calculations
- ✅ Model leaderboard calculations
- ✅ Time period filtering (hourly, daily, weekly)
- ✅ Real-time dashboard updates
- ✅ Data aggregation accuracy
- ✅ Monitoring API endpoints
- ✅ Data consistency across queries
- ✅ Error handling in monitoring

### Docker Deployment Tests
- ✅ Docker image build process
- ✅ Container startup and health
- ✅ Web UI port accessibility (4322)
- ✅ Proxy port accessibility (4321)
- ✅ Data persistence across restarts
- ✅ Environment variable configuration
- ✅ Docker Compose deployment
- ✅ Container resource usage
- ✅ Log accessibility
- ✅ Multiple container instances

## Requirements Coverage

The integration tests cover all requirements specified in the task:

### Requirement 1.1 (Configuration Web UI)
- ✅ Web UI accessibility on port 4322
- ✅ Authentication with initial password "Hakodate4"
- ✅ Service configuration workflow
- ✅ Model loading functionality

### Requirement 2.1 (Monitoring Dashboard)
- ✅ Usage statistics display
- ✅ Time period selection
- ✅ Client and model leaderboards
- ✅ Real-time updates

### Requirement 3.1 (Proxy Service)
- ✅ Proxy service on port 4321
- ✅ OpenAI-compatible API routing
- ✅ Multiple service support
- ✅ Response transformation

### Requirement 5.2 (Docker Deployment)
- ✅ Docker container functionality
- ✅ Port accessibility
- ✅ Data persistence
- ✅ Container orchestration

## Test Data and Mocking

### Mock Services
Tests use comprehensive mocking to avoid external API calls:
- Mock LiteLLM responses
- Mock HTTP requests to external services
- Mock database operations where appropriate
- Isolated test databases for each test

### Test Data
- Predefined service configurations for all supported types
- Sample usage records with known patterns
- Test user credentials and session data
- Mock API responses for model discovery

## Troubleshooting

### Common Issues

1. **Database Lock Errors**
   - Each test uses an isolated database
   - Ensure proper cleanup in test fixtures
   - Check for hanging database connections

2. **Port Conflicts**
   - Docker tests use different port mappings
   - Ensure no services running on test ports
   - Use `docker ps` to check for conflicting containers

3. **Docker Not Available**
   - Use `--skip-docker` flag to skip Docker tests
   - Install Docker if needed for complete test coverage

4. **Import Errors**
   - Ensure you're running from the `clads-llm-bridge` directory
   - Check that all dependencies are installed
   - Verify Python path includes the source directory

### Debug Mode

Run tests with maximum verbosity:
```bash
python tests/run_integration_tests.py --verbose
pytest tests/test_integration_*.py -v -s --tb=long
```

### Test Isolation

If tests interfere with each other:
```bash
# Run tests in separate processes
pytest tests/test_integration_*.py --forked

# Run specific test in isolation
pytest tests/test_integration_config_workflow.py::TestConfigurationWorkflowIntegration::test_complete_authentication_flow -v
```

## Continuous Integration

For CI/CD pipelines:

```bash
# Fast test run (no Docker)
python tests/run_integration_tests.py --skip-docker

# Full test run with coverage
pytest tests/test_integration_*.py --cov=src --cov-report=xml --cov-fail-under=80

# Generate test report
pytest tests/test_integration_*.py --junitxml=test-results.xml
```

## Contributing

When adding new integration tests:

1. Follow the existing test structure and naming conventions
2. Use appropriate pytest markers
3. Include comprehensive error handling tests
4. Mock external dependencies appropriately
5. Update this README with new test coverage
6. Ensure tests are deterministic and can run in any order