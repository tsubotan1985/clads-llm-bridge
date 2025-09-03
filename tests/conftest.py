"""
Pytest configuration and fixtures for integration tests.
"""

import pytest
import tempfile
import os
import shutil
from unittest.mock import patch
from src.database.init_db import initialize_database


@pytest.fixture(scope="session")
def test_data_dir():
    """Create a temporary directory for test data that persists for the session."""
    temp_dir = tempfile.mkdtemp(prefix="clads_test_")
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def isolated_db():
    """Create an isolated test database for each test."""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
        test_db_path = tmp.name
    
    # Initialize test database
    initialize_database(test_db_path)
    
    yield test_db_path
    
    # Cleanup
    if os.path.exists(test_db_path):
        try:
            os.unlink(test_db_path)
        except OSError:
            pass


@pytest.fixture
def mock_external_apis():
    """Mock external API calls to prevent real API requests during tests."""
    with patch('requests.get') as mock_get, \
         patch('requests.post') as mock_post, \
         patch('litellm.completion') as mock_completion:
        
        # Default mock responses
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {"models": ["test-model"]}
        
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {"success": True}
        
        mock_completion.return_value = {
            "id": "test-completion",
            "object": "chat.completion",
            "model": "test-model",
            "choices": [{
                "message": {"role": "assistant", "content": "Test response"},
                "finish_reason": "stop"
            }],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}
        }
        
        yield {
            "get": mock_get,
            "post": mock_post,
            "completion": mock_completion
        }


@pytest.fixture
def test_config():
    """Provide test configuration data."""
    return {
        "default_password": "Hakodate4",
        "test_services": [
            {
                "service_type": "openai",
                "api_key": "test-openai-key",
                "base_url": "https://api.openai.com/v1",
                "model_name": "gpt-3.5-turbo",
                "public_name": "Test OpenAI"
            },
            {
                "service_type": "anthropic",
                "api_key": "test-anthropic-key",
                "base_url": "https://api.anthropic.com",
                "model_name": "claude-3-sonnet-20240229",
                "public_name": "Test Anthropic"
            },
            {
                "service_type": "vscode_proxy",
                "api_key": "",
                "base_url": "http://localhost:3000",
                "model_name": "vscode-lm-proxy",
                "public_name": "Test VS Code"
            }
        ],
        "test_usage_records": [
            {
                "client_ip": "192.168.1.100",
                "model_name": "gpt-3.5-turbo",
                "public_name": "Test Model 1",
                "input_tokens": 100,
                "output_tokens": 50
            },
            {
                "client_ip": "192.168.1.101",
                "model_name": "gpt-4",
                "public_name": "Test Model 2",
                "input_tokens": 200,
                "output_tokens": 100
            }
        ]
    }


def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line(
        "markers", "integration: mark test as an integration test"
    )
    config.addinivalue_line(
        "markers", "docker: mark test as requiring Docker"
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow running"
    )


def pytest_collection_modifyitems(config, items):
    """Automatically mark integration tests."""
    for item in items:
        # Mark integration tests
        if "integration" in item.nodeid:
            item.add_marker(pytest.mark.integration)
        
        # Mark Docker tests
        if "docker" in item.nodeid:
            item.add_marker(pytest.mark.docker)
            item.add_marker(pytest.mark.slow)
        
        # Mark slow tests
        if any(keyword in item.nodeid for keyword in ["docker", "deployment", "monitoring_accuracy"]):
            item.add_marker(pytest.mark.slow)


@pytest.fixture(autouse=True)
def setup_test_environment():
    """Setup test environment for each test."""
    # Ensure we're in the right directory
    original_cwd = os.getcwd()
    
    # If we're in the tests directory, go up one level
    if os.path.basename(os.getcwd()) == "tests":
        os.chdir("..")
    
    yield
    
    # Restore original directory
    os.chdir(original_cwd)


@pytest.fixture
def clean_environment():
    """Provide a clean environment for tests that need isolation."""
    # Store original environment variables
    original_env = os.environ.copy()
    
    # Clear test-related environment variables
    test_env_vars = [
        "DATABASE_PATH",
        "LOG_LEVEL",
        "TEST_MODE"
    ]
    
    for var in test_env_vars:
        if var in os.environ:
            del os.environ[var]
    
    yield
    
    # Restore original environment
    os.environ.clear()
    os.environ.update(original_env)