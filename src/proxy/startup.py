"""Startup script for the LiteLLM proxy server."""

import asyncio
import logging
import signal
import sys
import threading
import time
from typing import Optional, Dict, Any
from pathlib import Path

from ..config.configuration_service import ConfigurationService
from ..database.connection import DatabaseConnection
from ..database.migrations import DatabaseMigrations
from ..database.init_db import initialize_database, verify_database_health, get_database_info
from .proxy_server import ProxyServer


logger = logging.getLogger(__name__)


class ProxyServerManager:
    """Manager for the proxy server lifecycle with enhanced startup and shutdown handling."""
    
    def __init__(self, db_path: str = None, port: int = 4321):
        """Initialize the proxy server manager.
        
        Args:
            db_path: Path to the database file
            port: Port to run the server on
        """
        self.db_path = db_path or "data/clads_llm_bridge.db"
        self.port = port
        self.config_service: Optional[ConfigurationService] = None
        self.proxy_server: Optional[ProxyServer] = None
        self._shutdown_event = threading.Event()
        self._startup_complete = False
        self._initialization_error: Optional[str] = None
        
    def initialize(self) -> bool:
        """Initialize the proxy server components with enhanced error handling.
        
        Returns:
            True if initialization successful, False otherwise
        """
        try:
            logger.info("Starting proxy server initialization...")
            
            # Ensure database directory exists
            db_file_path = Path(self.db_path)
            db_file_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Get database information for logging
            db_info = get_database_info(self.db_path)
            logger.info(f"Database info: {db_info}")
            
            # Initialize database with enhanced error handling
            logger.info("Initializing database for proxy server...")
            if not initialize_database(self.db_path):
                self._initialization_error = "Database initialization failed"
                return False
            
            # Verify database health
            if not verify_database_health(self.db_path):
                self._initialization_error = "Database health check failed"
                return False
            
            # Create configuration service
            logger.info("Creating configuration service...")
            self.config_service = ConfigurationService(self.db_path)
            
            # Load and validate startup configuration
            if not self._load_startup_configuration():
                self._initialization_error = "Configuration loading failed"
                return False
            
            # Create proxy server
            logger.info(f"Creating proxy server on port {self.port}...")
            self.proxy_server = ProxyServer(self.config_service, self.port)
            logger.info(f"Proxy server instance created successfully")
            
            # Pre-configure LiteLLM to catch configuration errors early
            logger.info("Pre-configuring LiteLLM adapter...")
            if not self.proxy_server.adapter.configure_litellm():
                logger.warning("LiteLLM configuration failed, but continuing startup")
                # Don't fail initialization for LiteLLM config issues
                # The proxy will handle this gracefully
            else:
                logger.info("LiteLLM adapter configured successfully")
            
            self._startup_complete = True
            logger.info(f"Proxy server initialization complete - ready to serve on 0.0.0.0:{self.port}")
            return True
            
        except Exception as e:
            self._initialization_error = str(e)
            logger.error(f"Error during proxy server initialization: {e}")
            logger.exception("Full error details:")
            return False
    
    def _load_startup_configuration(self) -> bool:
        """Load and validate startup configuration for LiteLLM.
        
        Returns:
            True if configuration loaded successfully, False otherwise
        """
        try:
            logger.info("Loading startup configuration for proxy server...")
            
            # Get all configurations
            all_configs = self.config_service.get_llm_configs()
            enabled_configs = self.config_service.get_enabled_configs()
            
            logger.info(f"Total configurations: {len(all_configs)}")
            logger.info(f"Enabled configurations: {len(enabled_configs)}")
            
            # Log configuration details
            for config in enabled_configs:
                logger.info(f"  - {config.service_type.value}: {config.public_name or config.model_name}")
                
                # Validate configuration
                validation_errors = self._validate_config(config)
                if validation_errors:
                    logger.warning(f"Configuration {config.id} has validation errors:")
                    for error in validation_errors:
                        logger.warning(f"    - {error}")
            
            # Check if we have at least one valid configuration
            valid_configs = [config for config in enabled_configs 
                           if not self._validate_config(config)]
            
            if not valid_configs:
                logger.warning("No valid configurations found, proxy will start but may not route requests")
            else:
                logger.info(f"Found {len(valid_configs)} valid configurations")
            
            return True
            
        except Exception as e:
            logger.error(f"Error loading startup configuration: {e}")
            return False
    
    def _validate_config(self, config) -> list:
        """Validate a single configuration.
        
        Args:
            config: LLM configuration to validate
            
        Returns:
            List of validation errors (empty if valid)
        """
        errors = []
        
        if not config.model_name:
            errors.append("Missing model name")
        
        if not config.service_type:
            errors.append("Missing service type")
        
        # Check API key requirements
        if (config.service_type.value not in ["none", "vscode_proxy", "lmstudio"] and 
            not config.api_key):
            errors.append(f"Missing API key for {config.service_type.value}")
        
        if not config.base_url and config.service_type.value in ["openai_compatible", "lmstudio"]:
            errors.append("Missing base URL for custom service")
        
        return errors
    
    def start_sync(self):
        """Start the proxy server synchronously with enhanced error handling."""
        if not self.initialize():
            logger.error(f"Proxy server initialization failed: {self._initialization_error}")
            sys.exit(1)
        
        # Setup signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        try:
            logger.info(f"Starting proxy server on port {self.port}...")
            
            # Start the server with graceful shutdown handling
            self.proxy_server.start_server()
            
        except KeyboardInterrupt:
            logger.info("Received interrupt signal, shutting down...")
            self.shutdown()
        except Exception as e:
            logger.error(f"Error running proxy server: {e}")
            logger.exception("Full error details:")
            self.shutdown()
            sys.exit(1)
    
    async def start_async(self):
        """Start the proxy server asynchronously with enhanced error handling."""
        if not self.initialize():
            logger.error(f"Proxy server initialization failed: {self._initialization_error}")
            return False
        
        try:
            logger.info(f"Starting proxy server asynchronously on 0.0.0.0:{self.port}...")
            logger.info(f"Database path: {self.db_path}")
            logger.info(f"Configuration service available: {self.config_service is not None}")
            
            # Start the server in a task
            logger.info("Creating proxy server task...")
            server_task = asyncio.create_task(self.proxy_server.start_server_async())
            
            # Create shutdown event task
            shutdown_task = asyncio.create_task(self._wait_for_shutdown())
            
            logger.info("Proxy server tasks created, waiting for completion or shutdown...")
            
            # Wait for shutdown signal or server completion
            done, pending = await asyncio.wait(
                [server_task, shutdown_task],
                return_when=asyncio.FIRST_COMPLETED
            )
            
            logger.info("Proxy server task completed or shutdown requested")
            
            # Cancel pending tasks
            for task in pending:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    logger.info(f"Task {task.get_name() if hasattr(task, 'get_name') else 'unknown'} cancelled")
            
            logger.info("Proxy server stopped gracefully")
            return True
            
        except Exception as e:
            logger.error(f"Error running proxy server: {e}")
            logger.exception("Full error details:")
            return False
    
    async def _wait_for_shutdown(self):
        """Wait for shutdown event asynchronously."""
        while not self._shutdown_event.is_set():
            await asyncio.sleep(0.1)
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals."""
        logger.info(f"Received signal {signum}, initiating graceful shutdown...")
        self.shutdown()
    
    def shutdown(self):
        """Shutdown the proxy server gracefully."""
        logger.info("Initiating graceful shutdown of proxy server...")
        
        try:
            # Set shutdown event
            self._shutdown_event.set()
            
            # Shutdown proxy server if it exists
            if self.proxy_server:
                logger.info("Shutting down proxy server...")
                # The proxy server should handle its own shutdown
                # when it detects the shutdown event
            
            # Close configuration service
            if self.config_service:
                logger.info("Closing configuration service...")
                # Configuration service cleanup if needed
            
            logger.info("Proxy server shutdown complete")
            
        except Exception as e:
            logger.error(f"Error during proxy server shutdown: {e}")
    
    def reload_configuration(self) -> bool:
        """Reload configuration from database.
        
        Returns:
            True if reload successful, False otherwise
        """
        try:
            logger.info("Reloading proxy server configuration...")
            
            if not self.proxy_server:
                logger.error("Proxy server not initialized")
                return False
            
            # Reload configuration in the proxy server
            success = self.proxy_server.reload_configuration()
            
            if success:
                logger.info("Configuration reloaded successfully")
            else:
                logger.error("Configuration reload failed")
            
            return success
            
        except Exception as e:
            logger.error(f"Error reloading configuration: {e}")
            return False
    
    def get_status(self) -> Dict[str, Any]:
        """Get proxy server status information.
        
        Returns:
            Dictionary with status information
        """
        return {
            "initialized": self._startup_complete,
            "initialization_error": self._initialization_error,
            "shutdown_requested": self._shutdown_event.is_set(),
            "port": self.port,
            "database_path": self.db_path,
            "proxy_server_running": self.proxy_server is not None,
            "config_service_available": self.config_service is not None
        }
    
    def is_healthy(self) -> bool:
        """Check if proxy server is healthy.
        
        Returns:
            True if healthy, False otherwise
        """
        return (self._startup_complete and 
                not self._shutdown_event.is_set() and 
                self.proxy_server is not None and 
                self.config_service is not None)


def main():
    """Main entry point for the proxy server."""
    import argparse
    
    parser = argparse.ArgumentParser(description="CLADS LLM Bridge Proxy Server")
    parser.add_argument("--port", type=int, default=4321, help="Port to run the server on")
    parser.add_argument("--db-path", type=str, help="Path to the database file")
    parser.add_argument("--log-level", type=str, default="INFO", 
                       choices=["DEBUG", "INFO", "WARNING", "ERROR"],
                       help="Logging level")
    
    args = parser.parse_args()
    
    # Configure logging
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    # Create and start server manager
    manager = ProxyServerManager(args.db_path, args.port)
    manager.start_sync()


if __name__ == "__main__":
    main()