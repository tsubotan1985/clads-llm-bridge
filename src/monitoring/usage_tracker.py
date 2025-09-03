"""Usage tracking service for CLADS LLM Bridge."""

import uuid
import logging
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from enum import Enum

from ..database.connection import DatabaseConnection
from ..models.usage_record import UsageRecord, UsageStats, ClientUsage, ModelUsage


logger = logging.getLogger(__name__)


class TimePeriod(Enum):
    """Time period options for statistics."""
    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"


class UsageTracker:
    """Service for tracking and analyzing API usage."""
    
    def __init__(self, db_path: str = None):
        """Initialize the usage tracker.
        
        Args:
            db_path: Path to the SQLite database file
        """
        self.db_path = db_path or "data/clads_llm_bridge.db"
        self.db = DatabaseConnection(self.db_path)
    
    def log_request(
        self,
        client_ip: str,
        model_name: str,
        public_name: str = "",
        input_tokens: int = 0,
        output_tokens: int = 0,
        response_time_ms: int = 0,
        status: str = "success",
        error_message: Optional[str] = None
    ) -> bool:
        """Log an API request for usage tracking.
        
        Args:
            client_ip: IP address of the client
            model_name: Name of the model used
            public_name: Public name of the model
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            response_time_ms: Response time in milliseconds
            status: Request status (success, error)
            error_message: Error message if status is error
            
        Returns:
            True if logging successful, False otherwise
        """
        try:
            usage_record = UsageRecord(
                id=str(uuid.uuid4()),
                timestamp=datetime.utcnow(),
                client_ip=client_ip,
                model_name=model_name,
                public_name=public_name,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                response_time_ms=response_time_ms,
                status=status,
                error_message=error_message
            )
            
            self.db.execute_update("""
                INSERT INTO usage_records 
                (id, timestamp, client_ip, model_name, public_name, 
                 input_tokens, output_tokens, total_tokens, response_time_ms, 
                 status, error_message)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                usage_record.id,
                usage_record.timestamp.isoformat(),
                usage_record.client_ip,
                usage_record.model_name,
                usage_record.public_name,
                usage_record.input_tokens,
                usage_record.output_tokens,
                usage_record.total_tokens,
                usage_record.response_time_ms,
                usage_record.status,
                usage_record.error_message
            ))
            
            return True
            
        except Exception as e:
            logger.error(f"Error logging usage: {e}")
            return False
    
    def log_usage(
        self,
        client_ip: str,
        model_name: str,
        public_name: str = "",
        input_tokens: int = 0,
        output_tokens: int = 0,
        response_time_ms: int = 0,
        status: str = "success",
        error_message: Optional[str] = None
    ) -> bool:
        """Alias for log_request method for backward compatibility.
        
        Args:
            client_ip: IP address of the client
            model_name: Name of the model used
            public_name: Public name of the model
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            response_time_ms: Response time in milliseconds
            status: Request status (success, error)
            error_message: Error message if status is error
            
        Returns:
            True if logging successful, False otherwise
        """
        return self.log_request(
            client_ip=client_ip,
            model_name=model_name,
            public_name=public_name,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            response_time_ms=response_time_ms,
            status=status,
            error_message=error_message
        )
    
    def get_usage_stats(self, period: TimePeriod, start_time: Optional[datetime] = None) -> UsageStats:
        """Get usage statistics for a time period.
        
        Args:
            period: Time period for statistics
            start_time: Start time for the period (defaults to appropriate time based on period)
            
        Returns:
            UsageStats object
        """
        try:
            # Calculate time range
            end_time = datetime.utcnow()
            if start_time is None:
                if period == TimePeriod.HOURLY:
                    start_time = end_time - timedelta(hours=1)
                elif period == TimePeriod.DAILY:
                    start_time = end_time - timedelta(days=1)
                elif period == TimePeriod.WEEKLY:
                    start_time = end_time - timedelta(weeks=1)
            
            # Optimized query using indexes
            stats_query = """
                SELECT 
                    COUNT(*) as total_requests,
                    COALESCE(SUM(total_tokens), 0) as total_tokens,
                    COALESCE(SUM(input_tokens), 0) as total_input_tokens,
                    COALESCE(SUM(output_tokens), 0) as total_output_tokens,
                    COALESCE(AVG(response_time_ms), 0) as avg_response_time,
                    COALESCE(SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) * 100.0 / NULLIF(COUNT(*), 0), 0) as success_rate
                FROM usage_records
                WHERE timestamp >= ? AND timestamp <= ?
            """
            
            result = self.db.execute_query(stats_query, (
                start_time.isoformat(),
                end_time.isoformat()
            ))
            
            if result and result[0]['total_requests'] > 0:
                row = result[0]
                return UsageStats(
                    total_requests=row['total_requests'],
                    total_tokens=row['total_tokens'],
                    total_input_tokens=row['total_input_tokens'],
                    total_output_tokens=row['total_output_tokens'],
                    average_response_time=row['avg_response_time'],
                    success_rate=row['success_rate'],
                    period_start=start_time,
                    period_end=end_time
                )
            
            return UsageStats(
                total_requests=0,
                period_start=start_time,
                period_end=end_time
            )
            
        except Exception as e:
            logger.error(f"Error getting usage stats: {e}")
            return UsageStats(
                total_requests=0,
                period_start=start_time or datetime.utcnow(),
                period_end=datetime.utcnow()
            )
    
    def get_client_leaderboard(self, period, limit: int = 10) -> List[ClientUsage]:
        """Get client usage leaderboard.
        
        Args:
            period: Time period for leaderboard (TimePeriod enum or "all" string)
            limit: Maximum number of clients to return
            
        Returns:
            List of ClientUsage objects sorted by total tokens
        """
        try:
            # Calculate time range
            end_time = datetime.utcnow()
            
            if period == "all":
                # Get all records
                start_time = datetime(1970, 1, 1)  # Very old date to include all records
            elif period == TimePeriod.HOURLY:
                start_time = end_time - timedelta(hours=1)
            elif period == TimePeriod.DAILY:
                start_time = end_time - timedelta(days=1)
            elif period == TimePeriod.WEEKLY:
                start_time = end_time - timedelta(weeks=1)
            else:
                # Default to daily if unknown period
                start_time = end_time - timedelta(days=1)
            
            # Query client usage
            client_query = """
                SELECT 
                    client_ip,
                    COUNT(*) as total_requests,
                    COALESCE(SUM(total_tokens), 0) as total_tokens,
                    COALESCE(SUM(input_tokens), 0) as total_input_tokens,
                    COALESCE(SUM(output_tokens), 0) as total_output_tokens,
                    COALESCE(AVG(response_time_ms), 0) as avg_response_time,
                    MAX(timestamp) as last_request
                FROM usage_records
                WHERE timestamp >= ? AND timestamp <= ?
                GROUP BY client_ip
                ORDER BY total_tokens DESC
                LIMIT ?
            """
            
            results = self.db.execute_query(client_query, (
                start_time.isoformat(),
                end_time.isoformat(),
                limit
            ))
            
            clients = []
            for row in results:
                clients.append(ClientUsage(
                    client_ip=row['client_ip'],
                    total_requests=row['total_requests'],
                    total_tokens=row['total_tokens'],
                    total_input_tokens=row['total_input_tokens'],
                    total_output_tokens=row['total_output_tokens'],
                    average_response_time=row['avg_response_time'],
                    last_request=datetime.fromisoformat(row['last_request'])
                ))
            
            return clients
            
        except Exception as e:
            logger.error(f"Error getting client leaderboard: {e}")
            return []
    
    def get_model_leaderboard(self, period, limit: int = 10) -> List[ModelUsage]:
        """Get model usage leaderboard.
        
        Args:
            period: Time period for leaderboard (TimePeriod enum or "all" string)
            limit: Maximum number of models to return
            
        Returns:
            List of ModelUsage objects sorted by total tokens
        """
        try:
            # Calculate time range
            end_time = datetime.utcnow()
            
            if period == "all":
                # Get all records
                start_time = datetime(1970, 1, 1)  # Very old date to include all records
            elif period == TimePeriod.HOURLY:
                start_time = end_time - timedelta(hours=1)
            elif period == TimePeriod.DAILY:
                start_time = end_time - timedelta(days=1)
            elif period == TimePeriod.WEEKLY:
                start_time = end_time - timedelta(weeks=1)
            else:
                # Default to daily if unknown period
                start_time = end_time - timedelta(days=1)
            
            # Query model usage
            model_query = """
                SELECT 
                    model_name,
                    public_name,
                    COUNT(*) as total_requests,
                    COALESCE(SUM(total_tokens), 0) as total_tokens,
                    COALESCE(SUM(input_tokens), 0) as total_input_tokens,
                    COALESCE(SUM(output_tokens), 0) as total_output_tokens,
                    COALESCE(AVG(response_time_ms), 0) as avg_response_time,
                    COUNT(DISTINCT client_ip) as unique_clients,
                    MAX(timestamp) as last_request
                FROM usage_records
                WHERE timestamp >= ? AND timestamp <= ?
                GROUP BY model_name, public_name
                ORDER BY total_tokens DESC
                LIMIT ?
            """
            
            results = self.db.execute_query(model_query, (
                start_time.isoformat(),
                end_time.isoformat(),
                limit
            ))
            
            models = []
            for row in results:
                models.append(ModelUsage(
                    model_name=row['model_name'],
                    public_name=row['public_name'] or row['model_name'],
                    total_requests=row['total_requests'],
                    total_tokens=row['total_tokens'],
                    total_input_tokens=row['total_input_tokens'],
                    total_output_tokens=row['total_output_tokens'],
                    average_response_time=row['avg_response_time'],
                    unique_clients=row['unique_clients'],
                    last_request=datetime.fromisoformat(row['last_request'])
                ))
            
            return models
            
        except Exception as e:
            logger.error(f"Error getting model leaderboard: {e}")
            return []
    
    def get_usage_records(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        client_ip: Optional[str] = None,
        model_name: Optional[str] = None,
        limit: int = 100
    ) -> List[UsageRecord]:
        """Get usage records with optional filtering.
        
        Args:
            start_time: Start time filter
            end_time: End time filter
            client_ip: Client IP filter
            model_name: Model name filter
            limit: Maximum number of records to return
            
        Returns:
            List of UsageRecord objects
        """
        try:
            # Build query with filters
            query = "SELECT * FROM usage_records WHERE 1=1"
            params = []
            
            if start_time:
                query += " AND timestamp >= ?"
                params.append(start_time.isoformat())
            
            if end_time:
                query += " AND timestamp <= ?"
                params.append(end_time.isoformat())
            
            if client_ip:
                query += " AND client_ip = ?"
                params.append(client_ip)
            
            if model_name:
                query += " AND model_name = ?"
                params.append(model_name)
            
            query += " ORDER BY timestamp DESC LIMIT ?"
            params.append(limit)
            
            results = self.db.execute_query(query, params)
            
            records = []
            for row in results:
                record_data = dict(row)
                record_data['timestamp'] = datetime.fromisoformat(record_data['timestamp'])
                records.append(UsageRecord(**record_data))
            
            return records
            
        except Exception as e:
            logger.error(f"Error getting usage records: {e}")
            return []
    
    def get_usage_stats_by_interval(
        self,
        period: TimePeriod,
        start_time: Optional[datetime] = None,
        interval_count: int = 24
    ) -> List[Dict[str, Any]]:
        """Get usage statistics broken down by time intervals.
        
        Args:
            period: Time period for statistics
            start_time: Start time for the period
            interval_count: Number of intervals to return
            
        Returns:
            List of dictionaries with interval statistics
        """
        try:
            # Calculate time range and interval size
            end_time = datetime.utcnow()
            if start_time is None:
                if period == TimePeriod.HOURLY:
                    start_time = end_time - timedelta(hours=interval_count)
                    interval_minutes = 60
                elif period == TimePeriod.DAILY:
                    start_time = end_time - timedelta(days=interval_count)
                    interval_minutes = 24 * 60
                elif period == TimePeriod.WEEKLY:
                    start_time = end_time - timedelta(weeks=interval_count)
                    interval_minutes = 7 * 24 * 60
            else:
                total_minutes = int((end_time - start_time).total_seconds() / 60)
                interval_minutes = total_minutes // interval_count
            
            # Query usage statistics by intervals
            # Using SQLite's datetime functions for interval grouping
            if period == TimePeriod.HOURLY:
                time_format = "%Y-%m-%d %H:00:00"
            elif period == TimePeriod.DAILY:
                time_format = "%Y-%m-%d 00:00:00"
            else:  # WEEKLY
                time_format = "%Y-%W"
            
            interval_query = """
                SELECT 
                    strftime(?, timestamp) as interval_key,
                    COUNT(*) as total_requests,
                    COALESCE(SUM(total_tokens), 0) as total_tokens,
                    COALESCE(SUM(input_tokens), 0) as total_input_tokens,
                    COALESCE(SUM(output_tokens), 0) as total_output_tokens,
                    COALESCE(AVG(response_time_ms), 0) as avg_response_time,
                    COALESCE(SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) * 100.0 / NULLIF(COUNT(*), 0), 0) as success_rate
                FROM usage_records
                WHERE timestamp >= ? AND timestamp <= ?
                GROUP BY strftime(?, timestamp)
                ORDER BY interval_key
                LIMIT ?
            """
            
            results = self.db.execute_query(interval_query, (
                time_format,
                start_time.isoformat(),
                end_time.isoformat(),
                time_format,
                interval_count
            ))
            
            intervals = []
            for row in results:
                intervals.append({
                    'interval': row['interval_key'],
                    'total_requests': row['total_requests'],
                    'total_tokens': row['total_tokens'],
                    'total_input_tokens': row['total_input_tokens'],
                    'total_output_tokens': row['total_output_tokens'],
                    'average_response_time': row['avg_response_time'],
                    'success_rate': row['success_rate']
                })
            
            return intervals
            
        except Exception as e:
            logger.error(f"Error getting usage stats by interval: {e}")
            return []
    
    def get_model_usage_trends(self, period: TimePeriod, model_name: str = None) -> List[Dict[str, Any]]:
        """Get model usage trends over time intervals.
        
        Args:
            period: Time period for trends
            model_name: Specific model to get trends for (optional)
            
        Returns:
            List of dictionaries with time interval and usage data
        """
        try:
            # Calculate time range and interval format
            end_time = datetime.utcnow()
            if period == TimePeriod.HOURLY:
                start_time = end_time - timedelta(hours=24)
                time_format = "%Y-%m-%d %H:00:00"
                interval_name = "hour"
            elif period == TimePeriod.DAILY:
                start_time = end_time - timedelta(days=30)
                time_format = "%Y-%m-%d 00:00:00"
                interval_name = "day"
            elif period == TimePeriod.WEEKLY:
                start_time = end_time - timedelta(weeks=12)
                time_format = "%Y-%W"
                interval_name = "week"
            
            # Build query with optional model filter
            base_query = """
                SELECT 
                    strftime(?, timestamp) as time_interval,
                    model_name,
                    public_name,
                    COUNT(*) as total_requests,
                    COALESCE(SUM(total_tokens), 0) as total_tokens,
                    COALESCE(SUM(input_tokens), 0) as total_input_tokens,
                    COALESCE(SUM(output_tokens), 0) as total_output_tokens,
                    COALESCE(AVG(response_time_ms), 0) as avg_response_time,
                    COUNT(DISTINCT client_ip) as unique_clients
                FROM usage_records
                WHERE timestamp >= ? AND timestamp <= ?
            """
            
            params = [time_format, start_time.isoformat(), end_time.isoformat()]
            
            if model_name:
                base_query += " AND model_name = ?"
                params.append(model_name)
            
            base_query += """
                GROUP BY strftime(?, timestamp), model_name, public_name
                ORDER BY time_interval, total_tokens DESC
            """
            params.append(time_format)
            
            results = self.db.execute_query(base_query, params)
            
            trends = []
            for row in results:
                trends.append({
                    'time_interval': row['time_interval'],
                    'interval_type': interval_name,
                    'model_name': row['model_name'],
                    'public_name': row['public_name'],
                    'total_requests': row['total_requests'],
                    'total_tokens': row['total_tokens'],
                    'total_input_tokens': row['total_input_tokens'],
                    'total_output_tokens': row['total_output_tokens'],
                    'average_response_time': row['avg_response_time'],
                    'unique_clients': row['unique_clients']
                })
            
            return trends
            
        except Exception as e:
            logger.error(f"Error getting model usage trends: {e}")
            return []
    
    def get_model_comparison(self, period: TimePeriod) -> Dict[str, Any]:
        """Get model comparison statistics.
        
        Args:
            period: Time period for comparison
            
        Returns:
            Dictionary with model comparison data
        """
        try:
            # Get model leaderboard
            models = self.get_model_leaderboard(period, limit=20)
            
            if not models:
                return {
                    'total_models': 0,
                    'models': [],
                    'summary': {
                        'most_used_model': None,
                        'fastest_model': None,
                        'most_clients_model': None
                    }
                }
            
            # Calculate summary statistics
            most_used = models[0] if models else None
            fastest_model = min(models, key=lambda m: m.average_response_time) if models else None
            most_clients = max(models, key=lambda m: m.unique_clients) if models else None
            
            return {
                'total_models': len(models),
                'models': [
                    {
                        'model_name': model.model_name,
                        'public_name': model.public_name,
                        'total_requests': model.total_requests,
                        'total_tokens': model.total_tokens,
                        'average_response_time': model.average_response_time,
                        'unique_clients': model.unique_clients,
                        'tokens_per_request': model.total_tokens / model.total_requests if model.total_requests > 0 else 0,
                        'last_request': model.last_request.isoformat() if model.last_request else None
                    }
                    for model in models
                ],
                'summary': {
                    'most_used_model': {
                        'name': most_used.public_name,
                        'tokens': most_used.total_tokens
                    } if most_used else None,
                    'fastest_model': {
                        'name': fastest_model.public_name,
                        'response_time': fastest_model.average_response_time
                    } if fastest_model else None,
                    'most_clients_model': {
                        'name': most_clients.public_name,
                        'clients': most_clients.unique_clients
                    } if most_clients else None
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting model comparison: {e}")
            return {
                'total_models': 0,
                'models': [],
                'summary': {},
                'error': str(e)
            }
    
    def get_real_time_stats(self) -> Dict[str, Any]:
        """Get real-time usage statistics for the last few minutes.
        
        Returns:
            Dictionary with real-time statistics
        """
        try:
            now = datetime.utcnow()
            last_5_minutes = now - timedelta(minutes=5)
            last_hour = now - timedelta(hours=1)
            
            # Get stats for last 5 minutes
            recent_query = """
                SELECT 
                    COUNT(*) as requests_last_5min,
                    COALESCE(SUM(total_tokens), 0) as tokens_last_5min,
                    COALESCE(AVG(response_time_ms), 0) as avg_response_time_5min,
                    COUNT(DISTINCT client_ip) as unique_clients_5min
                FROM usage_records
                WHERE timestamp >= ?
            """
            
            recent_result = self.db.execute_query(recent_query, (last_5_minutes.isoformat(),))
            
            # Get stats for last hour
            hourly_query = """
                SELECT 
                    COUNT(*) as requests_last_hour,
                    COALESCE(SUM(total_tokens), 0) as tokens_last_hour,
                    COUNT(DISTINCT client_ip) as unique_clients_hour,
                    COUNT(DISTINCT model_name) as unique_models_hour
                FROM usage_records
                WHERE timestamp >= ?
            """
            
            hourly_result = self.db.execute_query(hourly_query, (last_hour.isoformat(),))
            
            # Get current error rate
            error_query = """
                SELECT 
                    COALESCE(SUM(CASE WHEN status = 'error' THEN 1 ELSE 0 END) * 100.0 / NULLIF(COUNT(*), 0), 0) as error_rate
                FROM usage_records
                WHERE timestamp >= ?
            """
            
            error_result = self.db.execute_query(error_query, (last_hour.isoformat(),))
            
            # Combine results
            stats = {
                'timestamp': now.isoformat(),
                'requests_last_5min': recent_result[0]['requests_last_5min'] if recent_result else 0,
                'tokens_last_5min': recent_result[0]['tokens_last_5min'] if recent_result else 0,
                'avg_response_time_5min': recent_result[0]['avg_response_time_5min'] if recent_result else 0,
                'unique_clients_5min': recent_result[0]['unique_clients_5min'] if recent_result else 0,
                'requests_last_hour': hourly_result[0]['requests_last_hour'] if hourly_result else 0,
                'tokens_last_hour': hourly_result[0]['tokens_last_hour'] if hourly_result else 0,
                'unique_clients_hour': hourly_result[0]['unique_clients_hour'] if hourly_result else 0,
                'unique_models_hour': hourly_result[0]['unique_models_hour'] if hourly_result else 0,
                'error_rate_hour': error_result[0]['error_rate'] if error_result else 0
            }
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting real-time stats: {e}")
            return {
                'timestamp': datetime.utcnow().isoformat(),
                'error': str(e)
            }
    
    def cleanup_old_records(self, days_to_keep: int = 30) -> int:
        """Clean up old usage records.
        
        Args:
            days_to_keep: Number of days of records to keep
            
        Returns:
            Number of records deleted
        """
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days_to_keep)
            
            deleted_count = self.db.execute_update(
                "DELETE FROM usage_records WHERE timestamp < ?",
                (cutoff_date.isoformat(),)
            )
            
            logger.info(f"Cleaned up {deleted_count} old usage records")
            return deleted_count
            
        except Exception as e:
            logger.error(f"Error cleaning up old records: {e}")
            return 0
    
    def get_total_usage(self) -> Dict[str, Any]:
        """Get total usage statistics across all time.
        
        Returns:
            Dictionary containing total usage statistics
        """
        try:
            # Get total statistics
            total_rows = self.db.execute_query("""
                SELECT 
                    COUNT(*) as total_requests,
                    SUM(input_tokens) as total_input_tokens,
                    SUM(output_tokens) as total_output_tokens,
                    SUM(total_tokens) as total_tokens,
                    AVG(response_time_ms) as avg_response_time,
                    COUNT(CASE WHEN status = 'success' THEN 1 END) as successful_requests
                FROM usage_records
            """)
            
            if not total_rows:
                return {
                    "total_requests": 0,
                    "total_input_tokens": 0,
                    "total_output_tokens": 0,
                    "total_tokens": 0,
                    "avg_response_time": 0,
                    "success_rate": 0
                }
            
            row = total_rows[0]
            total_requests = row['total_requests'] or 0
            success_rate = (row['successful_requests'] / total_requests * 100) if total_requests > 0 else 0
            
            return {
                "total_requests": total_requests,
                "total_input_tokens": row['total_input_tokens'] or 0,
                "total_output_tokens": row['total_output_tokens'] or 0,
                "total_tokens": row['total_tokens'] or 0,
                "avg_response_time": row['avg_response_time'] or 0,
                "success_rate": success_rate
            }
            
        except Exception as e:
            logger.error(f"Error getting total usage: {e}")
            return {
                "total_requests": 0,
                "total_input_tokens": 0,
                "total_output_tokens": 0,
                "total_tokens": 0,
                "avg_response_time": 0,
                "success_rate": 0
            }