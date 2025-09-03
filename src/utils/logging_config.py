"""Logging configuration for CLADS LLM Bridge."""

import logging
import logging.handlers
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional


class ColoredFormatter(logging.Formatter):
    """Colored formatter for console output."""
    
    # Color codes
    COLORS = {
        'DEBUG': '\033[36m',      # Cyan
        'INFO': '\033[32m',       # Green
        'WARNING': '\033[33m',    # Yellow
        'ERROR': '\033[31m',      # Red
        'CRITICAL': '\033[35m',   # Magenta
        'RESET': '\033[0m'        # Reset
    }
    
    def format(self, record):
        """Format log record with colors."""
        if hasattr(record, 'levelname'):
            color = self.COLORS.get(record.levelname, self.COLORS['RESET'])
            record.levelname = f"{color}{record.levelname}{self.COLORS['RESET']}"
        
        return super().format(record)


class StructuredFormatter(logging.Formatter):
    """Structured formatter for file output."""
    
    def format(self, record):
        """Format log record with structured information."""
        # Add timestamp
        record.timestamp = datetime.utcnow().isoformat()
        
        # Add process info
        record.process_name = record.processName
        record.thread_name = record.threadName
        
        # Add module info
        if hasattr(record, 'module'):
            record.component = record.module
        else:
            record.component = record.name.split('.')[-1]
        
        return super().format(record)


class LoggingConfig:
    """Centralized logging configuration."""
    
    def __init__(
        self,
        log_level: str = "INFO",
        log_dir: str = "logs",
        max_file_size: int = 10 * 1024 * 1024,  # 10MB
        backup_count: int = 5,
        enable_console: bool = True,
        enable_file: bool = True
    ):
        """Initialize logging configuration.
        
        Args:
            log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
            log_dir: Directory for log files
            max_file_size: Maximum size of each log file in bytes
            backup_count: Number of backup files to keep
            enable_console: Whether to enable console logging
            enable_file: Whether to enable file logging
        """
        self.log_level = getattr(logging, log_level.upper(), logging.INFO)
        self.log_dir = Path(log_dir)
        self.max_file_size = max_file_size
        self.backup_count = backup_count
        self.enable_console = enable_console
        self.enable_file = enable_file
        
        # Create log directory
        if self.enable_file:
            self.log_dir.mkdir(exist_ok=True)
        
        # Configure logging
        self._setup_logging()
    
    def _setup_logging(self):
        """Setup logging configuration."""
        # Get root logger
        root_logger = logging.getLogger()
        root_logger.setLevel(self.log_level)
        
        # Clear existing handlers
        root_logger.handlers.clear()
        
        # Console handler
        if self.enable_console:
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setLevel(self.log_level)
            
            console_formatter = ColoredFormatter(
                fmt='%(asctime)s | %(levelname)-8s | %(name)-20s | %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            console_handler.setFormatter(console_formatter)
            root_logger.addHandler(console_handler)
        
        # File handlers
        if self.enable_file:
            # Main application log
            app_handler = logging.handlers.RotatingFileHandler(
                filename=self.log_dir / "clads_llm_bridge.log",
                maxBytes=self.max_file_size,
                backupCount=self.backup_count,
                encoding='utf-8'
            )
            app_handler.setLevel(self.log_level)
            
            app_formatter = StructuredFormatter(
                fmt='%(timestamp)s | %(levelname)-8s | %(component)-15s | %(process_name)-10s | %(thread_name)-10s | %(message)s'
            )
            app_handler.setFormatter(app_formatter)
            root_logger.addHandler(app_handler)
            
            # Error log (ERROR and CRITICAL only)
            error_handler = logging.handlers.RotatingFileHandler(
                filename=self.log_dir / "errors.log",
                maxBytes=self.max_file_size,
                backupCount=self.backup_count,
                encoding='utf-8'
            )
            error_handler.setLevel(logging.ERROR)
            error_handler.setFormatter(app_formatter)
            root_logger.addHandler(error_handler)
            
            # Access log for web requests
            access_handler = logging.handlers.RotatingFileHandler(
                filename=self.log_dir / "access.log",
                maxBytes=self.max_file_size,
                backupCount=self.backup_count,
                encoding='utf-8'
            )
            access_handler.setLevel(logging.INFO)
            
            access_formatter = StructuredFormatter(
                fmt='%(timestamp)s | %(message)s'
            )
            access_handler.setFormatter(access_formatter)
            
            # Create access logger
            access_logger = logging.getLogger('access')
            access_logger.setLevel(logging.INFO)
            access_logger.addHandler(access_handler)
            access_logger.propagate = False
            
            # API log for proxy requests
            api_handler = logging.handlers.RotatingFileHandler(
                filename=self.log_dir / "api.log",
                maxBytes=self.max_file_size,
                backupCount=self.backup_count,
                encoding='utf-8'
            )
            api_handler.setLevel(logging.INFO)
            api_handler.setFormatter(app_formatter)
            
            # Create API logger
            api_logger = logging.getLogger('api')
            api_logger.setLevel(logging.INFO)
            api_logger.addHandler(api_handler)
            api_logger.propagate = False
    
    def get_logger(self, name: str) -> logging.Logger:
        """Get a logger with the specified name.
        
        Args:
            name: Logger name
            
        Returns:
            Configured logger instance
        """
        return logging.getLogger(name)
    
    def get_access_logger(self) -> logging.Logger:
        """Get the access logger for web requests.
        
        Returns:
            Access logger instance
        """
        return logging.getLogger('access')
    
    def get_api_logger(self) -> logging.Logger:
        """Get the API logger for proxy requests.
        
        Returns:
            API logger instance
        """
        return logging.getLogger('api')


class RequestLogger:
    """Logger for HTTP requests."""
    
    def __init__(self, logger: logging.Logger):
        """Initialize request logger.
        
        Args:
            logger: Logger instance to use
        """
        self.logger = logger
    
    def log_request(
        self,
        method: str,
        path: str,
        status_code: int,
        response_time_ms: float,
        client_ip: str = "unknown",
        user_agent: str = "unknown",
        content_length: Optional[int] = None
    ):
        """Log HTTP request.
        
        Args:
            method: HTTP method
            path: Request path
            status_code: HTTP status code
            response_time_ms: Response time in milliseconds
            client_ip: Client IP address
            user_agent: User agent string
            content_length: Response content length
        """
        message = (
            f"{client_ip} - \"{method} {path}\" {status_code} "
            f"{content_length or '-'} {response_time_ms:.2f}ms \"{user_agent}\""
        )
        
        if status_code >= 500:
            self.logger.error(message)
        elif status_code >= 400:
            self.logger.warning(message)
        else:
            self.logger.info(message)
    
    def log_api_request(
        self,
        service: str,
        model: str,
        method: str,
        endpoint: str,
        status_code: int,
        response_time_ms: float,
        input_tokens: int = 0,
        output_tokens: int = 0,
        client_ip: str = "unknown",
        error_message: Optional[str] = None
    ):
        """Log API proxy request.
        
        Args:
            service: Service name (openai, anthropic, etc.)
            model: Model name
            method: HTTP method
            endpoint: API endpoint
            status_code: HTTP status code
            response_time_ms: Response time in milliseconds
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            client_ip: Client IP address
            error_message: Error message if request failed
        """
        message = (
            f"API {service}/{model} - {client_ip} - \"{method} {endpoint}\" "
            f"{status_code} {response_time_ms:.2f}ms "
            f"tokens(in:{input_tokens}, out:{output_tokens})"
        )
        
        if error_message:
            message += f" - Error: {error_message}"
        
        if status_code >= 500:
            self.logger.error(message)
        elif status_code >= 400:
            self.logger.warning(message)
        else:
            self.logger.info(message)


class ErrorLogger:
    """Logger for errors and exceptions."""
    
    def __init__(self, logger: logging.Logger):
        """Initialize error logger.
        
        Args:
            logger: Logger instance to use
        """
        self.logger = logger
    
    def log_exception(
        self,
        exception: Exception,
        context: Optional[str] = None,
        extra_data: Optional[dict] = None
    ):
        """Log exception with context.
        
        Args:
            exception: Exception to log
            context: Additional context information
            extra_data: Extra data to include in log
        """
        message = f"Exception occurred: {type(exception).__name__}: {str(exception)}"
        
        if context:
            message = f"{context} - {message}"
        
        if extra_data:
            message += f" | Extra data: {extra_data}"
        
        self.logger.exception(message)
    
    def log_validation_error(
        self,
        field: str,
        value: str,
        error_message: str,
        form_type: str = "unknown"
    ):
        """Log validation error.
        
        Args:
            field: Field name that failed validation
            value: Value that failed (will be masked if sensitive)
            error_message: Validation error message
            form_type: Type of form being validated
        """
        # Mask sensitive values
        if field.lower() in ['password', 'api_key', 'secret', 'token']:
            value = "***MASKED***"
        
        message = f"Validation error in {form_type} form - Field: {field}, Value: {value}, Error: {error_message}"
        self.logger.warning(message)
    
    def log_configuration_error(
        self,
        config_id: str,
        service_type: str,
        error_message: str,
        operation: str = "unknown"
    ):
        """Log configuration error.
        
        Args:
            config_id: Configuration ID
            service_type: Service type
            error_message: Error message
            operation: Operation being performed
        """
        message = f"Configuration error - Operation: {operation}, Config: {config_id}, Service: {service_type}, Error: {error_message}"
        self.logger.error(message)
    
    def log_api_error(
        self,
        service: str,
        endpoint: str,
        status_code: int,
        error_message: str,
        client_ip: str = "unknown"
    ):
        """Log API error.
        
        Args:
            service: Service name
            endpoint: API endpoint
            status_code: HTTP status code
            error_message: Error message
            client_ip: Client IP address
        """
        message = f"API error - Service: {service}, Endpoint: {endpoint}, Status: {status_code}, Client: {client_ip}, Error: {error_message}"
        self.logger.error(message)


# Global logging configuration
_logging_config: Optional[LoggingConfig] = None


def setup_logging(
    log_level: str = None,
    log_dir: str = None,
    enable_console: bool = True,
    enable_file: bool = True
) -> LoggingConfig:
    """Setup global logging configuration.
    
    Args:
        log_level: Logging level from environment or default
        log_dir: Log directory from environment or default
        enable_console: Whether to enable console logging
        enable_file: Whether to enable file logging
        
    Returns:
        LoggingConfig instance
    """
    global _logging_config
    
    # Get configuration from environment variables
    log_level = log_level or os.getenv('LOG_LEVEL', 'INFO')
    log_dir = log_dir or os.getenv('LOG_DIR', 'logs')
    
    _logging_config = LoggingConfig(
        log_level=log_level,
        log_dir=log_dir,
        enable_console=enable_console,
        enable_file=enable_file
    )
    
    return _logging_config


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance.
    
    Args:
        name: Logger name
        
    Returns:
        Logger instance
    """
    if _logging_config is None:
        setup_logging()
    
    return _logging_config.get_logger(name)


def get_access_logger() -> logging.Logger:
    """Get the access logger.
    
    Returns:
        Access logger instance
    """
    if _logging_config is None:
        setup_logging()
    
    return _logging_config.get_access_logger()


def get_api_logger() -> logging.Logger:
    """Get the API logger.
    
    Returns:
        API logger instance
    """
    if _logging_config is None:
        setup_logging()
    
    return _logging_config.get_api_logger()


def get_request_logger() -> RequestLogger:
    """Get a request logger instance.
    
    Returns:
        RequestLogger instance
    """
    return RequestLogger(get_access_logger())


def get_error_logger() -> ErrorLogger:
    """Get an error logger instance.
    
    Returns:
        ErrorLogger instance
    """
    return ErrorLogger(get_logger('error'))