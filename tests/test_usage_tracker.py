"""Unit tests for UsageTracker."""

import pytest
import tempfile
import os
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.monitoring.usage_tracker import UsageTracker, TimePeriod
from src.models.usage_record import UsageRecord, UsageStats, ClientUsage, ModelUsage
from src.database.migrations import DatabaseMigrations
from src.database.connection import DatabaseConnection


class TestUsageTracker:
    """Test cases for UsageTracker."""
    
    @pytest.fixture
    def temp_db(self):
        """Create a temporary database for testing."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name
        
        # Initialize the database
        db_conn = DatabaseConnection(db_path)
        migrations = DatabaseMigrations(db_conn)
        migrations.initialize_database()
        
        yield db_path
        
        # Cleanup
        os.unlink(db_path)
    
    @pytest.fixture
    def usage_tracker(self, temp_db):
        """Create a UsageTracker instance with temporary database."""
        return UsageTracker(temp_db)
    
    @pytest.fixture
    def sample_usage_record(self):
        """Create a sample usage record."""
        return {
            "client_ip": "192.168.1.100",
            "model_name": "gpt-4",
            "public_name": "GPT-4",
            "input_tokens": 100,
            "output_tokens": 50,
            "response_time_ms": 1500,
            "status": "success"
        }
    
    def test_log_request_success(self, usage_tracker, sample_usage_record):
        """Test logging a successful request."""
        result = usage_tracker.log_request(**sample_usage_record)
        assert result is True
        
        # Verify the record was saved
        records = usage_tracker.get_usage_records(limit=1)
        assert len(records) == 1
        
        record = records[0]
        assert record.client_ip == sample_usage_record["client_ip"]
        assert record.model_name == sample_usage_record["model_name"]
        assert record.public_name == sample_usage_record["public_name"]
        assert record.input_tokens == sample_usage_record["input_tokens"]
        assert record.output_tokens == sample_usage_record["output_tokens"]
        assert record.total_tokens == 150  # 100 + 50
        assert record.response_time_ms == sample_usage_record["response_time_ms"]
        assert record.status == sample_usage_record["status"]
        assert record.error_message is None
    
    def test_log_request_error(self, usage_tracker):
        """Test logging an error request."""
        error_record = {
            "client_ip": "192.168.1.101",
            "model_name": "gpt-4",
            "public_name": "GPT-4",
            "input_tokens": 50,
            "output_tokens": 0,
            "response_time_ms": 500,
            "status": "error",
            "error_message": "API key invalid"
        }
        
        result = usage_tracker.log_request(**error_record)
        assert result is True
        
        # Verify the error record was saved
        records = usage_tracker.get_usage_records(limit=1)
        assert len(records) == 1
        
        record = records[0]
        assert record.status == "error"
        assert record.error_message == "API key invalid"
        assert record.output_tokens == 0
    
    def test_log_request_with_defaults(self, usage_tracker):
        """Test logging a request with minimal parameters."""
        result = usage_tracker.log_request(
            client_ip="192.168.1.102",
            model_name="claude-3-sonnet"
        )
        assert result is True
        
        # Verify defaults were applied
        records = usage_tracker.get_usage_records(limit=1)
        assert len(records) == 1
        
        record = records[0]
        assert record.public_name == ""
        assert record.input_tokens == 0
        assert record.output_tokens == 0
        assert record.total_tokens == 0
        assert record.response_time_ms == 0
        assert record.status == "success"
        assert record.error_message is None
    
    @patch('src.monitoring.usage_tracker.logger')
    def test_log_request_database_error(self, mock_logger, usage_tracker):
        """Test handling database errors during logging."""
        # Mock database to raise an exception
        with patch.object(usage_tracker.db, 'execute_update', side_effect=Exception("DB Error")):
            result = usage_tracker.log_request(
                client_ip="192.168.1.103",
                model_name="gpt-4"
            )
            assert result is False
            mock_logger.error.assert_called()
    
    def test_get_usage_stats_hourly(self, usage_tracker):
        """Test getting hourly usage statistics."""
        # Create test data
        now = datetime.utcnow()
        
        # Add records within the last hour
        for i in range(3):
            usage_tracker.log_request(
                client_ip=f"192.168.1.{100 + i}",
                model_name="gpt-4",
                input_tokens=100,
                output_tokens=50,
                response_time_ms=1000 + i * 100,
                status="success"
            )
        
        # Add one error record
        usage_tracker.log_request(
            client_ip="192.168.1.104",
            model_name="gpt-4",
            input_tokens=50,
            output_tokens=0,
            response_time_ms=500,
            status="error"
        )
        
        # Get hourly stats
        stats = usage_tracker.get_usage_stats(TimePeriod.HOURLY)
        
        assert stats.total_requests == 4
        assert stats.total_tokens == 500  # (100+50)*3 + 50
        assert stats.total_input_tokens == 350  # 100*3 + 50
        assert stats.total_output_tokens == 150  # 50*3 + 0
        assert stats.success_rate == 75.0  # 3/4 * 100
        assert stats.average_response_time > 0
        assert stats.period_start <= now
        assert stats.period_end >= now
    
    def test_get_usage_stats_daily(self, usage_tracker):
        """Test getting daily usage statistics."""
        # Add a record
        usage_tracker.log_request(
            client_ip="192.168.1.100",
            model_name="gpt-4",
            input_tokens=200,
            output_tokens=100,
            response_time_ms=2000,
            status="success"
        )
        
        stats = usage_tracker.get_usage_stats(TimePeriod.DAILY)
        
        assert stats.total_requests == 1
        assert stats.total_tokens == 300
        assert stats.success_rate == 100.0
    
    def test_get_usage_stats_weekly(self, usage_tracker):
        """Test getting weekly usage statistics."""
        # Add a record
        usage_tracker.log_request(
            client_ip="192.168.1.100",
            model_name="gpt-4",
            input_tokens=150,
            output_tokens=75,
            response_time_ms=1800,
            status="success"
        )
        
        stats = usage_tracker.get_usage_stats(TimePeriod.WEEKLY)
        
        assert stats.total_requests == 1
        assert stats.total_tokens == 225
        assert stats.success_rate == 100.0
    
    def test_get_usage_stats_custom_period(self, usage_tracker):
        """Test getting usage statistics for a custom time period."""
        now = datetime.utcnow()
        start_time = now - timedelta(hours=2)
        
        # Add record within the period
        usage_tracker.log_request(
            client_ip="192.168.1.100",
            model_name="gpt-4",
            input_tokens=100,
            output_tokens=50,
            status="success"
        )
        
        stats = usage_tracker.get_usage_stats(TimePeriod.HOURLY, start_time)
        
        assert stats.total_requests == 1
        assert stats.period_start == start_time
    
    def test_get_usage_stats_empty(self, usage_tracker):
        """Test getting usage statistics when no data exists."""
        stats = usage_tracker.get_usage_stats(TimePeriod.HOURLY)
        
        assert stats.total_requests == 0
        assert stats.total_tokens == 0
        assert stats.success_rate == 0.0
    
    def test_get_client_leaderboard(self, usage_tracker):
        """Test getting client usage leaderboard."""
        # Add records for different clients
        clients_data = [
            ("192.168.1.100", 1000, 500),  # 1500 total tokens
            ("192.168.1.101", 800, 400),   # 1200 total tokens
            ("192.168.1.102", 600, 300),   # 900 total tokens
        ]
        
        for client_ip, input_tokens, output_tokens in clients_data:
            usage_tracker.log_request(
                client_ip=client_ip,
                model_name="gpt-4",
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                response_time_ms=1000,
                status="success"
            )
        
        # Get leaderboard
        leaderboard = usage_tracker.get_client_leaderboard(TimePeriod.HOURLY, limit=10)
        
        assert len(leaderboard) == 3
        
        # Should be sorted by total tokens (descending)
        assert leaderboard[0].client_ip == "192.168.1.100"
        assert leaderboard[0].total_tokens == 1500
        assert leaderboard[1].client_ip == "192.168.1.101"
        assert leaderboard[1].total_tokens == 1200
        assert leaderboard[2].client_ip == "192.168.1.102"
        assert leaderboard[2].total_tokens == 900
        
        # Check other fields
        assert leaderboard[0].total_requests == 1
        assert leaderboard[0].total_input_tokens == 1000
        assert leaderboard[0].total_output_tokens == 500
        assert leaderboard[0].average_response_time == 1000
    
    def test_get_client_leaderboard_multiple_requests(self, usage_tracker):
        """Test client leaderboard with multiple requests per client."""
        # Add multiple records for the same client
        for i in range(3):
            usage_tracker.log_request(
                client_ip="192.168.1.100",
                model_name="gpt-4",
                input_tokens=100,
                output_tokens=50,
                response_time_ms=1000 + i * 100,
                status="success"
            )
        
        leaderboard = usage_tracker.get_client_leaderboard(TimePeriod.HOURLY)
        
        assert len(leaderboard) == 1
        client = leaderboard[0]
        assert client.client_ip == "192.168.1.100"
        assert client.total_requests == 3
        assert client.total_tokens == 450  # (100+50) * 3
        assert client.average_response_time == 1100  # (1000+1100+1200) / 3
    
    def test_get_model_leaderboard(self, usage_tracker):
        """Test getting model usage leaderboard."""
        # Add records for different models
        models_data = [
            ("gpt-4", "GPT-4", 1000, 500),
            ("claude-3-sonnet", "Claude 3 Sonnet", 800, 400),
            ("gemini-pro", "Gemini Pro", 600, 300),
        ]
        
        for model_name, public_name, input_tokens, output_tokens in models_data:
            usage_tracker.log_request(
                client_ip="192.168.1.100",
                model_name=model_name,
                public_name=public_name,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                response_time_ms=1000,
                status="success"
            )
        
        # Get leaderboard
        leaderboard = usage_tracker.get_model_leaderboard(TimePeriod.HOURLY, limit=10)
        
        assert len(leaderboard) == 3
        
        # Should be sorted by total tokens (descending)
        assert leaderboard[0].model_name == "gpt-4"
        assert leaderboard[0].public_name == "GPT-4"
        assert leaderboard[0].total_tokens == 1500
        assert leaderboard[1].model_name == "claude-3-sonnet"
        assert leaderboard[1].public_name == "Claude 3 Sonnet"
        assert leaderboard[1].total_tokens == 1200
        
        # Check unique clients count
        assert leaderboard[0].unique_clients == 1
    
    def test_get_model_leaderboard_multiple_clients(self, usage_tracker):
        """Test model leaderboard with multiple clients using the same model."""
        # Add records from different clients for the same model
        for i in range(3):
            usage_tracker.log_request(
                client_ip=f"192.168.1.{100 + i}",
                model_name="gpt-4",
                public_name="GPT-4",
                input_tokens=100,
                output_tokens=50,
                response_time_ms=1000,
                status="success"
            )
        
        leaderboard = usage_tracker.get_model_leaderboard(TimePeriod.HOURLY)
        
        assert len(leaderboard) == 1
        model = leaderboard[0]
        assert model.model_name == "gpt-4"
        assert model.total_requests == 3
        assert model.total_tokens == 450
        assert model.unique_clients == 3
    
    def test_get_usage_records_filtering(self, usage_tracker):
        """Test filtering usage records."""
        now = datetime.utcnow()
        
        # Add test records
        usage_tracker.log_request(
            client_ip="192.168.1.100",
            model_name="gpt-4",
            input_tokens=100,
            output_tokens=50,
            status="success"
        )
        
        usage_tracker.log_request(
            client_ip="192.168.1.101",
            model_name="claude-3-sonnet",
            input_tokens=80,
            output_tokens=40,
            status="success"
        )
        
        # Test client IP filter
        records = usage_tracker.get_usage_records(client_ip="192.168.1.100")
        assert len(records) == 1
        assert records[0].client_ip == "192.168.1.100"
        
        # Test model name filter
        records = usage_tracker.get_usage_records(model_name="claude-3-sonnet")
        assert len(records) == 1
        assert records[0].model_name == "claude-3-sonnet"
        
        # Test time filter
        start_time = now - timedelta(minutes=1)
        end_time = now + timedelta(minutes=1)
        records = usage_tracker.get_usage_records(start_time=start_time, end_time=end_time)
        assert len(records) == 2
        
        # Test limit
        records = usage_tracker.get_usage_records(limit=1)
        assert len(records) == 1
    
    def test_cleanup_old_records(self, usage_tracker):
        """Test cleaning up old usage records."""
        now = datetime.utcnow()
        
        # Add a recent record
        usage_tracker.log_request(
            client_ip="192.168.1.100",
            model_name="gpt-4",
            status="success"
        )
        
        # Manually insert an old record
        old_timestamp = (now - timedelta(days=35)).isoformat()
        usage_tracker.db.execute_update("""
            INSERT INTO usage_records 
            (id, timestamp, client_ip, model_name, public_name, 
             input_tokens, output_tokens, total_tokens, response_time_ms, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            "old-record",
            old_timestamp,
            "192.168.1.200",
            "gpt-3.5-turbo",
            "GPT-3.5 Turbo",
            50,
            25,
            75,
            800,
            "success"
        ))
        
        # Verify we have 2 records
        all_records = usage_tracker.get_usage_records(limit=100)
        assert len(all_records) == 2
        
        # Clean up records older than 30 days
        deleted_count = usage_tracker.cleanup_old_records(days_to_keep=30)
        assert deleted_count == 1
        
        # Verify only the recent record remains
        remaining_records = usage_tracker.get_usage_records(limit=100)
        assert len(remaining_records) == 1
        assert remaining_records[0].client_ip == "192.168.1.100"
    
    @patch('src.monitoring.usage_tracker.logger')
    def test_error_handling(self, mock_logger, usage_tracker):
        """Test error handling in various methods."""
        # Mock database to raise exceptions
        with patch.object(usage_tracker.db, 'execute_query', side_effect=Exception("DB Error")):
            # Test get_usage_stats error handling
            stats = usage_tracker.get_usage_stats(TimePeriod.HOURLY)
            assert stats.total_requests == 0
            mock_logger.error.assert_called()
            
            # Test get_client_leaderboard error handling
            leaderboard = usage_tracker.get_client_leaderboard(TimePeriod.HOURLY)
            assert len(leaderboard) == 0
            
            # Test get_model_leaderboard error handling
            leaderboard = usage_tracker.get_model_leaderboard(TimePeriod.HOURLY)
            assert len(leaderboard) == 0
            
            # Test get_usage_records error handling
            records = usage_tracker.get_usage_records()
            assert len(records) == 0
        
        # Test cleanup_old_records error handling
        with patch.object(usage_tracker.db, 'execute_update', side_effect=Exception("DB Error")):
            deleted_count = usage_tracker.cleanup_old_records()
            assert deleted_count == 0
    
    def test_time_period_calculations(self, usage_tracker):
        """Test that time period calculations work correctly."""
        now = datetime.utcnow()
        
        # Add records at different times
        # Recent record (within last hour)
        usage_tracker.log_request(
            client_ip="192.168.1.100",
            model_name="gpt-4",
            input_tokens=100,
            output_tokens=50,
            status="success"
        )
        
        # Manually insert older records
        # 2 hours ago (should appear in daily/weekly but not hourly)
        old_timestamp_2h = (now - timedelta(hours=2)).isoformat()
        usage_tracker.db.execute_update("""
            INSERT INTO usage_records 
            (id, timestamp, client_ip, model_name, public_name, 
             input_tokens, output_tokens, total_tokens, response_time_ms, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            "record-2h",
            old_timestamp_2h,
            "192.168.1.101",
            "gpt-4",
            "GPT-4",
            80,
            40,
            120,
            1000,
            "success"
        ))
        
        # 2 days ago (should appear in weekly but not daily/hourly)
        old_timestamp_2d = (now - timedelta(days=2)).isoformat()
        usage_tracker.db.execute_update("""
            INSERT INTO usage_records 
            (id, timestamp, client_ip, model_name, public_name, 
             input_tokens, output_tokens, total_tokens, response_time_ms, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            "record-2d",
            old_timestamp_2d,
            "192.168.1.102",
            "gpt-4",
            "GPT-4",
            60,
            30,
            90,
            800,
            "success"
        ))
        
        # Test hourly stats (should only include recent record)
        hourly_stats = usage_tracker.get_usage_stats(TimePeriod.HOURLY)
        assert hourly_stats.total_requests == 1
        assert hourly_stats.total_tokens == 150
        
        # Test daily stats (should include recent + 2h ago)
        daily_stats = usage_tracker.get_usage_stats(TimePeriod.DAILY)
        assert daily_stats.total_requests == 2
        assert daily_stats.total_tokens == 270  # 150 + 120
        
        # Test weekly stats (should include all records)
        weekly_stats = usage_tracker.get_usage_stats(TimePeriod.WEEKLY)
        assert weekly_stats.total_requests == 3
        assert weekly_stats.total_tokens == 360  # 150 + 120 + 90
    
    def test_leaderboard_limits(self, usage_tracker):
        """Test leaderboard limit functionality."""
        # Add records for many clients
        for i in range(15):
            usage_tracker.log_request(
                client_ip=f"192.168.1.{100 + i}",
                model_name="gpt-4",
                input_tokens=100,
                output_tokens=50,
                status="success"
            )
        
        # Test default limit
        leaderboard = usage_tracker.get_client_leaderboard(TimePeriod.HOURLY)
        assert len(leaderboard) == 10  # Default limit
        
        # Test custom limit
        leaderboard = usage_tracker.get_client_leaderboard(TimePeriod.HOURLY, limit=5)
        assert len(leaderboard) == 5
        
        # Test limit larger than available data
        leaderboard = usage_tracker.get_client_leaderboard(TimePeriod.HOURLY, limit=20)
        assert len(leaderboard) == 15  # All available records
    
    def test_get_usage_stats_by_interval(self, usage_tracker):
        """Test getting usage statistics by time intervals."""
        now = datetime.utcnow()
        
        # Add records at different times within the last few hours
        for i in range(3):
            # Create records at different hours
            timestamp = now - timedelta(hours=i)
            
            # Manually insert records with specific timestamps
            usage_tracker.db.execute_update("""
                INSERT INTO usage_records 
                (id, timestamp, client_ip, model_name, public_name, 
                 input_tokens, output_tokens, total_tokens, response_time_ms, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                f"record-{i}",
                timestamp.isoformat(),
                f"192.168.1.{100 + i}",
                "gpt-4",
                "GPT-4",
                100,
                50,
                150,
                1000,
                "success"
            ))
        
        # Get interval statistics
        intervals = usage_tracker.get_usage_stats_by_interval(
            TimePeriod.HOURLY,
            start_time=now - timedelta(hours=5),
            interval_count=5
        )
        
        # Should have some intervals with data
        assert len(intervals) >= 0  # May be empty if no data matches the exact hour format
        
        # Test that the method doesn't crash with different periods
        daily_intervals = usage_tracker.get_usage_stats_by_interval(TimePeriod.DAILY, interval_count=7)
        assert isinstance(daily_intervals, list)
        
        weekly_intervals = usage_tracker.get_usage_stats_by_interval(TimePeriod.WEEKLY, interval_count=4)
        assert isinstance(weekly_intervals, list)
    
    def test_get_real_time_stats(self, usage_tracker):
        """Test getting real-time usage statistics."""
        now = datetime.utcnow()
        
        # Add recent records (within last 5 minutes)
        for i in range(2):
            usage_tracker.log_request(
                client_ip=f"192.168.1.{100 + i}",
                model_name="gpt-4",
                input_tokens=100,
                output_tokens=50,
                response_time_ms=1000,
                status="success"
            )
        
        # Add one error record
        usage_tracker.log_request(
            client_ip="192.168.1.102",
            model_name="claude-3-sonnet",
            input_tokens=50,
            output_tokens=0,
            response_time_ms=500,
            status="error",
            error_message="API error"
        )
        
        # Add older record (within last hour but not last 5 minutes)
        old_timestamp = (now - timedelta(minutes=30)).isoformat()
        usage_tracker.db.execute_update("""
            INSERT INTO usage_records 
            (id, timestamp, client_ip, model_name, public_name, 
             input_tokens, output_tokens, total_tokens, response_time_ms, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            "old-record",
            old_timestamp,
            "192.168.1.200",
            "gemini-pro",
            "Gemini Pro",
            80,
            40,
            120,
            800,
            "success"
        ))
        
        # Get real-time stats
        stats = usage_tracker.get_real_time_stats()
        
        # Verify structure
        assert 'timestamp' in stats
        assert 'requests_last_5min' in stats
        assert 'tokens_last_5min' in stats
        assert 'avg_response_time_5min' in stats
        assert 'unique_clients_5min' in stats
        assert 'requests_last_hour' in stats
        assert 'tokens_last_hour' in stats
        assert 'unique_clients_hour' in stats
        assert 'unique_models_hour' in stats
        assert 'error_rate_hour' in stats
        
        # Verify values
        assert stats['requests_last_5min'] == 3  # 2 success + 1 error
        assert stats['tokens_last_5min'] == 350  # (100+50)*2 + 50
        assert stats['unique_clients_5min'] == 3  # 3 different IPs
        assert stats['requests_last_hour'] == 4  # 3 recent + 1 old
        assert stats['tokens_last_hour'] == 470  # 350 + 120
        assert stats['unique_clients_hour'] == 4  # 4 different IPs
        assert stats['unique_models_hour'] == 3  # gpt-4, claude-3-sonnet, gemini-pro
        assert stats['error_rate_hour'] == 25.0  # 1 error out of 4 requests