"""
Integration tests for usage tracking and monitoring dashboard accuracy.
Tests the complete flow from usage logging to dashboard display.
"""

import pytest
import tempfile
import os
import time
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from src.web.app import WebApp
from src.monitoring.usage_tracker import UsageTracker
from src.config.configuration_service import ConfigurationService
from src.database.init_db import initialize_database
from src.models.enums import ServiceType


@pytest.fixture
def test_db():
    """Create a temporary test database."""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
        test_db_path = tmp.name
    
    initialize_database(test_db_path)
    yield test_db_path
    
    if os.path.exists(test_db_path):
        os.unlink(test_db_path)


@pytest.fixture
def usage_tracker(test_db):
    """Create usage tracker with test database."""
    with patch('src.database.connection.get_db_path', return_value=test_db):
        return UsageTracker()


@pytest.fixture
def config_service(test_db):
    """Create configuration service with test database."""
    with patch('src.database.connection.get_db_path', return_value=test_db):
        return ConfigurationService()


@pytest.fixture
def client(test_db):
    """Create test client with temporary database."""
    with patch('src.database.connection.get_db_path', return_value=test_db):
        web_app = WebApp()
        with TestClient(web_app.app) as test_client:
            yield test_client


class TestMonitoringAccuracyIntegration:
    """Test usage tracking and monitoring dashboard accuracy."""
    
    def test_usage_logging_accuracy(self, usage_tracker):
        """Test accuracy of usage logging."""
        # Log multiple usage records with different patterns
        test_records = [
            {
                "client_ip": "192.168.1.100",
                "model_name": "gpt-3.5-turbo",
                "public_name": "OpenAI GPT-3.5",
                "input_tokens": 100,
                "output_tokens": 50,
                "response_time_ms": 1500
            },
            {
                "client_ip": "192.168.1.101",
                "model_name": "gpt-3.5-turbo",
                "public_name": "OpenAI GPT-3.5",
                "input_tokens": 200,
                "output_tokens": 75,
                "response_time_ms": 2000
            },
            {
                "client_ip": "192.168.1.100",
                "model_name": "claude-3-sonnet-20240229",
                "public_name": "Claude 3 Sonnet",
                "input_tokens": 150,
                "output_tokens": 100,
                "response_time_ms": 1800
            },
            {
                "client_ip": "192.168.1.102",
                "model_name": "gpt-4",
                "public_name": "OpenAI GPT-4",
                "input_tokens": 80,
                "output_tokens": 120,
                "response_time_ms": 3000
            }
        ]
        
        # Log all records
        for record in test_records:
            usage_tracker.log_usage(
                client_ip=record["client_ip"],
                model_name=record["model_name"],
                public_name=record["public_name"],
                input_tokens=record["input_tokens"],
                output_tokens=record["output_tokens"],
                response_time_ms=record["response_time_ms"]
            )
        
        # Verify total usage
        total_stats = usage_tracker.get_total_usage()
        assert total_stats["total_requests"] == 4
        assert total_stats["total_input_tokens"] == 530  # 100+200+150+80
        assert total_stats["total_output_tokens"] == 345  # 50+75+100+120
        assert total_stats["total_tokens"] == 875  # 530+345
    
    def test_client_leaderboard_accuracy(self, usage_tracker):
        """Test accuracy of client leaderboard calculations."""
        # Create usage data with known patterns
        usage_data = [
            ("192.168.1.100", "gpt-3.5-turbo", "OpenAI GPT-3.5", 100, 50),  # Total: 150
            ("192.168.1.100", "gpt-4", "OpenAI GPT-4", 200, 100),  # Total: 300, Client total: 450
            ("192.168.1.101", "claude-3-sonnet-20240229", "Claude 3", 300, 150),  # Total: 450
            ("192.168.1.102", "gpt-3.5-turbo", "OpenAI GPT-3.5", 50, 25),  # Total: 75
            ("192.168.1.101", "gpt-3.5-turbo", "OpenAI GPT-3.5", 80, 40),  # Total: 120, Client total: 570
        ]
        
        for ip, model, public_name, input_tokens, output_tokens in usage_data:
            usage_tracker.log_usage(
                client_ip=ip,
                model_name=model,
                public_name=public_name,
                input_tokens=input_tokens,
                output_tokens=output_tokens
            )
        
        # Get client leaderboard
        leaderboard = usage_tracker.get_client_leaderboard(period="all")
        
        # Verify rankings (should be sorted by total tokens descending)
        assert len(leaderboard) == 3
        
        # Client 192.168.1.101 should be first (570 tokens)
        assert leaderboard[0]["client_ip"] == "192.168.1.101"
        assert leaderboard[0]["total_tokens"] == 570
        assert leaderboard[0]["request_count"] == 2
        
        # Client 192.168.1.100 should be second (450 tokens)
        assert leaderboard[1]["client_ip"] == "192.168.1.100"
        assert leaderboard[1]["total_tokens"] == 450
        assert leaderboard[1]["request_count"] == 2
        
        # Client 192.168.1.102 should be third (75 tokens)
        assert leaderboard[2]["client_ip"] == "192.168.1.102"
        assert leaderboard[2]["total_tokens"] == 75
        assert leaderboard[2]["request_count"] == 1
    
    def test_model_leaderboard_accuracy(self, usage_tracker):
        """Test accuracy of model leaderboard calculations."""
        # Create usage data with known model patterns
        usage_data = [
            ("192.168.1.100", "gpt-3.5-turbo", "OpenAI GPT-3.5", 100, 50),  # Model total: 150
            ("192.168.1.101", "gpt-3.5-turbo", "OpenAI GPT-3.5", 200, 100),  # Model total: 450
            ("192.168.1.102", "gpt-3.5-turbo", "OpenAI GPT-3.5", 50, 25),  # Model total: 525
            ("192.168.1.100", "claude-3-sonnet-20240229", "Claude 3", 300, 200),  # Model total: 500
            ("192.168.1.101", "gpt-4", "OpenAI GPT-4", 150, 75),  # Model total: 225
        ]
        
        for ip, model, public_name, input_tokens, output_tokens in usage_data:
            usage_tracker.log_usage(
                client_ip=ip,
                model_name=model,
                public_name=public_name,
                input_tokens=input_tokens,
                output_tokens=output_tokens
            )
        
        # Get model leaderboard
        leaderboard = usage_tracker.get_model_leaderboard(period="all")
        
        # Verify rankings (should be sorted by total tokens descending)
        assert len(leaderboard) == 3
        
        # OpenAI GPT-3.5 should be first (525 tokens)
        assert leaderboard[0]["public_name"] == "OpenAI GPT-3.5"
        assert leaderboard[0]["total_tokens"] == 525
        assert leaderboard[0]["request_count"] == 3
        
        # Claude 3 should be second (500 tokens)
        assert leaderboard[1]["public_name"] == "Claude 3"
        assert leaderboard[1]["total_tokens"] == 500
        assert leaderboard[1]["request_count"] == 1
        
        # OpenAI GPT-4 should be third (225 tokens)
        assert leaderboard[2]["public_name"] == "OpenAI GPT-4"
        assert leaderboard[2]["total_tokens"] == 225
        assert leaderboard[2]["request_count"] == 1
    
    def test_time_period_filtering_accuracy(self, usage_tracker):
        """Test accuracy of time period filtering."""
        now = datetime.now()
        
        # Create usage records with different timestamps
        usage_records = [
            # Recent (within last hour)
            (now - timedelta(minutes=30), "192.168.1.100", "gpt-3.5-turbo", "Recent Model", 100, 50),
            (now - timedelta(minutes=45), "192.168.1.101", "gpt-4", "Recent Model 2", 200, 100),
            
            # Yesterday
            (now - timedelta(days=1), "192.168.1.100", "claude-3-sonnet-20240229", "Yesterday Model", 150, 75),
            
            # Last week
            (now - timedelta(days=7), "192.168.1.102", "gpt-3.5-turbo", "Old Model", 300, 150),
        ]
        
        # Mock datetime.now() in usage tracker to control timestamps
        with patch('src.monitoring.usage_tracker.datetime') as mock_datetime:
            for timestamp, ip, model, public_name, input_tokens, output_tokens in usage_records:
                mock_datetime.now.return_value = timestamp
                usage_tracker.log_usage(
                    client_ip=ip,
                    model_name=model,
                    public_name=public_name,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens
                )
        
        # Test hourly filtering
        hourly_stats = usage_tracker.get_usage_stats(period="hourly")
        assert hourly_stats["total_requests"] == 2  # Only recent records
        assert hourly_stats["total_tokens"] == 450  # 150 + 300
        
        # Test daily filtering
        daily_stats = usage_tracker.get_usage_stats(period="daily")
        assert daily_stats["total_requests"] == 3  # Recent + yesterday
        assert daily_stats["total_tokens"] == 675  # 150 + 300 + 225
        
        # Test weekly filtering (all records)
        weekly_stats = usage_tracker.get_usage_stats(period="weekly")
        assert weekly_stats["total_requests"] == 4  # All records
        assert weekly_stats["total_tokens"] == 1125  # All tokens
    
    def test_monitoring_dashboard_integration(self, client, usage_tracker):
        """Test monitoring dashboard displays accurate data."""
        # Login first
        login_response = client.post("/login", data={"password": "Hakodate4"})
        cookies = login_response.cookies
        
        # Create test usage data
        test_data = [
            ("192.168.1.100", "gpt-3.5-turbo", "Test Model 1", 100, 50),
            ("192.168.1.101", "gpt-4", "Test Model 2", 200, 100),
            ("192.168.1.100", "claude-3-sonnet-20240229", "Test Model 3", 150, 75),
        ]
        
        for ip, model, public_name, input_tokens, output_tokens in test_data:
            usage_tracker.log_usage(
                client_ip=ip,
                model_name=model,
                public_name=public_name,
                input_tokens=input_tokens,
                output_tokens=output_tokens
            )
        
        # Test monitoring page loads
        response = client.get("/monitoring", cookies=cookies)
        assert response.status_code == 200
        
        # Test monitoring API endpoints
        response = client.get("/api/usage_stats?period=daily", cookies=cookies)
        assert response.status_code == 200
        
        data = response.json()
        assert "total_requests" in data
        assert "total_tokens" in data
        assert data["total_requests"] == 3
        assert data["total_tokens"] == 675  # 150 + 300 + 225
        
        # Test client leaderboard API
        response = client.get("/api/client_leaderboard?period=daily", cookies=cookies)
        assert response.status_code == 200
        
        leaderboard = response.json()
        assert len(leaderboard) == 2  # Two unique IPs
        
        # Test model leaderboard API
        response = client.get("/api/model_leaderboard?period=daily", cookies=cookies)
        assert response.status_code == 200
        
        model_leaderboard = response.json()
        assert len(model_leaderboard) == 3  # Three unique models
    
    def test_real_time_updates_accuracy(self, client, usage_tracker):
        """Test real-time updates reflect accurate data."""
        # Login first
        login_response = client.post("/login", data={"password": "Hakodate4"})
        cookies = login_response.cookies
        
        # Initial state - no usage
        response = client.get("/api/usage_stats?period=daily", cookies=cookies)
        initial_data = response.json()
        initial_requests = initial_data.get("total_requests", 0)
        
        # Add usage record
        usage_tracker.log_usage(
            client_ip="192.168.1.100",
            model_name="gpt-3.5-turbo",
            public_name="Real-time Test Model",
            input_tokens=100,
            output_tokens=50
        )
        
        # Check updated stats
        response = client.get("/api/usage_stats?period=daily", cookies=cookies)
        updated_data = response.json()
        
        assert updated_data["total_requests"] == initial_requests + 1
        assert updated_data["total_tokens"] == 150
        
        # Add another record from different client
        usage_tracker.log_usage(
            client_ip="192.168.1.101",
            model_name="gpt-4",
            public_name="Real-time Test Model 2",
            input_tokens=200,
            output_tokens=100
        )
        
        # Check leaderboards updated
        response = client.get("/api/client_leaderboard?period=daily", cookies=cookies)
        client_leaderboard = response.json()
        
        assert len(client_leaderboard) == 2
        # Should be sorted by total tokens
        assert client_leaderboard[0]["total_tokens"] >= client_leaderboard[1]["total_tokens"]
    
    def test_usage_aggregation_accuracy(self, usage_tracker):
        """Test accuracy of usage data aggregation functions."""
        # Create complex usage pattern
        usage_pattern = [
            # Same client, different models
            ("192.168.1.100", "gpt-3.5-turbo", "GPT-3.5", 100, 50),
            ("192.168.1.100", "gpt-4", "GPT-4", 200, 100),
            ("192.168.1.100", "claude-3-sonnet-20240229", "Claude", 150, 75),
            
            # Different client, same model
            ("192.168.1.101", "gpt-3.5-turbo", "GPT-3.5", 80, 40),
            ("192.168.1.102", "gpt-3.5-turbo", "GPT-3.5", 120, 60),
            
            # Unique combinations
            ("192.168.1.103", "gpt-4", "GPT-4", 300, 150),
        ]
        
        for ip, model, public_name, input_tokens, output_tokens in usage_pattern:
            usage_tracker.log_usage(
                client_ip=ip,
                model_name=model,
                public_name=public_name,
                input_tokens=input_tokens,
                output_tokens=output_tokens
            )
        
        # Test aggregation by client
        client_stats = usage_tracker.get_client_stats()
        
        # Client 192.168.1.100 should have 3 requests, 825 total tokens
        client_100_stats = next((c for c in client_stats if c["client_ip"] == "192.168.1.100"), None)
        assert client_100_stats is not None
        assert client_100_stats["request_count"] == 3
        assert client_100_stats["total_tokens"] == 675  # (100+50)+(200+100)+(150+75)
        
        # Test aggregation by model
        model_stats = usage_tracker.get_model_stats()
        
        # GPT-3.5 should have 3 requests from different clients
        gpt35_stats = next((m for m in model_stats if m["public_name"] == "GPT-3.5"), None)
        assert gpt35_stats is not None
        assert gpt35_stats["request_count"] == 3
        assert gpt35_stats["total_tokens"] == 450  # (100+50)+(80+40)+(120+60)
        
        # GPT-4 should have 2 requests
        gpt4_stats = next((m for m in model_stats if m["public_name"] == "GPT-4"), None)
        assert gpt4_stats is not None
        assert gpt4_stats["request_count"] == 2
        assert gpt4_stats["total_tokens"] == 750  # (200+100)+(300+150)
    
    def test_error_handling_in_monitoring(self, client, usage_tracker):
        """Test error handling in monitoring functionality."""
        # Login first
        login_response = client.post("/login", data={"password": "Hakodate4"})
        cookies = login_response.cookies
        
        # Test invalid period parameter
        response = client.get("/api/usage_stats?period=invalid", cookies=cookies)
        # Should handle gracefully, either return error or default to valid period
        assert response.status_code in [200, 400]
        
        # Test monitoring page with no data
        response = client.get("/monitoring", cookies=cookies)
        assert response.status_code == 200
        
        # Test API endpoints with no data
        response = client.get("/api/client_leaderboard?period=daily", cookies=cookies)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)  # Should return empty list, not error
        
        response = client.get("/api/model_leaderboard?period=daily", cookies=cookies)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)  # Should return empty list, not error
    
    def test_monitoring_data_consistency(self, usage_tracker):
        """Test consistency of monitoring data across different queries."""
        # Add consistent test data
        test_records = [
            ("192.168.1.100", "gpt-3.5-turbo", "Model A", 100, 50),
            ("192.168.1.101", "gpt-4", "Model B", 200, 100),
            ("192.168.1.100", "claude-3-sonnet-20240229", "Model C", 150, 75),
        ]
        
        for ip, model, public_name, input_tokens, output_tokens in test_records:
            usage_tracker.log_usage(
                client_ip=ip,
                model_name=model,
                public_name=public_name,
                input_tokens=input_tokens,
                output_tokens=output_tokens
            )
        
        # Get data from different methods
        total_stats = usage_tracker.get_total_usage()
        client_leaderboard = usage_tracker.get_client_leaderboard(period="all")
        model_leaderboard = usage_tracker.get_model_leaderboard(period="all")
        
        # Verify consistency
        # Total requests should match sum of client requests
        client_total_requests = sum(client.total_requests for client in client_leaderboard)
        assert total_stats["total_requests"] == client_total_requests
        
        # Total requests should match sum of model requests
        model_total_requests = sum(model.total_requests for model in model_leaderboard)
        assert total_stats["total_requests"] == model_total_requests
        
        # Total tokens should match sum of client tokens
        client_total_tokens = sum(client.total_tokens for client in client_leaderboard)
        assert total_stats["total_tokens"] == client_total_tokens
        
        # Total tokens should match sum of model tokens
        model_total_tokens = sum(model.total_tokens for model in model_leaderboard)
        assert total_stats["total_tokens"] == model_total_tokens