#!/usr/bin/env python3
"""
CLADS LLM Bridge Server
Main entry point for the application
"""

import asyncio
import logging
import uvicorn
from pathlib import Path
import threading
import time
import os
import signal
import sys
import atexit
from typing import Optional
from dotenv import load_dotenv

from src.web.app import WebApp
from src.database.init_db import initialize_database
from src.proxy.startup import ProxyServerManager
from src.config.configuration_service import ConfigurationService

# Load environment variables from .env file if it exists
load_dotenv()

# Get configuration from environment variables
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO').upper()
WEB_UI_PORT = int(os.getenv('WEB_UI_PORT', '4322'))
PROXY_PORT = int(os.getenv('PROXY_PORT', '4321'))
DATA_DIR = os.getenv('DATA_DIR', 'data')
DATABASE_PATH = os.getenv('DATABASE_PATH', f'{DATA_DIR}/clads_llm_bridge.db')

# Setup logging with more detailed format for debugging
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format='%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

# Set specific log levels for external libraries to reduce noise
logging.getLogger("uvicorn").setLevel(logging.INFO)
logging.getLogger("uvicorn.access").setLevel(logging.INFO)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("litellm").setLevel(logging.INFO)

logger = logging.getLogger(__name__)

# Global variables for graceful shutdown
proxy_manager: Optional[ProxyServerManager] = None
web_server: Optional[uvicorn.Server] = None
shutdown_event = threading.Event()


class ApplicationStartup:
    """Handles application startup sequence and configuration persistence."""
    
    def __init__(self):
        """Initialize startup manager."""
        self.data_dir = Path(DATA_DIR)
        self.database_path = DATABASE_PATH
        self.config_service: Optional[ConfigurationService] = None
        
    def initialize_environment(self) -> bool:
        """Initialize application environment.
        
        Returns:
            True if initialization successful, False otherwise
        """
        try:
            logger.info("Initializing application environment...")
            
            # Create data directory if it doesn't exist
            self.data_dir.mkdir(exist_ok=True)
            logger.info(f"Data directory: {self.data_dir.absolute()}")
            
            # Ensure database file permissions
            db_file = Path(self.database_path)
            if db_file.exists():
                # Set appropriate permissions for database file
                os.chmod(db_file, 0o644)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize environment: {e}")
            return False
    
    def initialize_database(self) -> bool:
        """Initialize database with proper error handling.
        
        Returns:
            True if initialization successful, False otherwise
        """
        try:
            logger.info("Initializing database...")
            
            # Call the existing database initialization
            initialize_database(self.database_path)
            
            # Verify database is accessible
            self.config_service = ConfigurationService(self.database_path)
            
            # Test database connection
            configs = self.config_service.get_llm_configs()
            logger.info(f"Database initialized successfully. Found {len(configs)} configurations.")
            
            return True
            
        except Exception as e:
            logger.error(f"Database initialization failed: {e}")
            return False
    
    def load_startup_configuration(self) -> bool:
        """Load and validate startup configuration for LiteLLM.
        
        Returns:
            True if configuration loaded successfully, False otherwise
        """
        try:
            logger.info("Loading startup configuration...")
            
            if not self.config_service:
                self.config_service = ConfigurationService(self.database_path)
            
            # Get enabled configurations
            enabled_configs = self.config_service.get_enabled_configs()
            logger.info(f"Found {len(enabled_configs)} enabled LLM configurations")
            
            # Log configuration summary
            for config in enabled_configs:
                logger.info(f"  - {config.service_type.value}: {config.public_name or config.model_name}")
            
            # Validate configurations
            invalid_configs = []
            for config in enabled_configs:
                if not config.model_name:
                    invalid_configs.append(f"{config.id}: Missing model name")
                elif config.service_type.value != "none" and not config.api_key and config.service_type.value != "vscode_proxy":
                    invalid_configs.append(f"{config.id}: Missing API key for {config.service_type.value}")
            
            if invalid_configs:
                logger.warning("Found invalid configurations:")
                for invalid in invalid_configs:
                    logger.warning(f"  - {invalid}")
                logger.warning("These configurations will be skipped during proxy startup")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to load startup configuration: {e}")
            return False


def setup_signal_handlers():
    """Setup signal handlers for graceful shutdown."""
    def signal_handler(signum, frame):
        logger.info(f"Received signal {signum}, initiating graceful shutdown...")
        shutdown_event.set()
    
    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Register cleanup function
    atexit.register(cleanup_on_exit)


def cleanup_on_exit():
    """Cleanup function called on exit."""
    logger.info("Performing cleanup on exit...")
    
    if proxy_manager:
        try:
            proxy_manager.shutdown()
        except Exception as e:
            logger.error(f"Error during proxy cleanup: {e}")
    
    logger.info("Cleanup completed")


async def start_proxy_server_async(startup_manager: ApplicationStartup, port: int):
    """Start the proxy server asynchronously.
    
    Args:
        startup_manager: Application startup manager
        port: Port to run proxy server on
    """
    global proxy_manager
    
    try:
        logger.info(f"Starting LiteLLM proxy server on port {port}...")
        proxy_manager = ProxyServerManager(startup_manager.database_path, port=port)
        
        # Load configuration before starting
        if not proxy_manager.initialize():
            logger.error("Failed to initialize proxy server")
            return False
        
        # Start the proxy server asynchronously
        await proxy_manager.start_async()
        return True
        
    except Exception as e:
        logger.error(f"Error starting proxy server: {e}")
        logger.exception("Full error details:")
        shutdown_event.set()
        return False


def create_health_check_app() -> uvicorn.Server:
    """Create a simple health check server for container orchestration.
    
    Returns:
        Configured uvicorn server for health checks
    """
    from fastapi import FastAPI
    
    health_app = FastAPI(title="CLADS LLM Bridge Health Check")
    
    @health_app.get("/health")
    async def health_check():
        """Container orchestration health check endpoint."""
        try:
            # Check if both services are running
            web_healthy = web_server is not None and not shutdown_event.is_set()
            proxy_healthy = proxy_manager is not None and not shutdown_event.is_set()
            
            if web_healthy and proxy_healthy:
                return {
                    "status": "healthy",
                    "services": {
                        "web_ui": {"status": "running", "port": WEB_UI_PORT},
                        "proxy": {"status": "running", "port": PROXY_PORT}
                    },
                    "timestamp": time.time()
                }
            else:
                return {
                    "status": "unhealthy",
                    "services": {
                        "web_ui": {"status": "running" if web_healthy else "stopped", "port": WEB_UI_PORT},
                        "proxy": {"status": "running" if proxy_healthy else "stopped", "port": PROXY_PORT}
                    },
                    "timestamp": time.time()
                }
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "timestamp": time.time()
            }
    
    @health_app.get("/health/ready")
    async def readiness_check():
        """Kubernetes readiness probe endpoint."""
        try:
            # Check if services are ready to accept traffic
            if proxy_manager and web_server and not shutdown_event.is_set():
                return {"status": "ready", "timestamp": time.time()}
            else:
                return {"status": "not_ready", "timestamp": time.time()}
        except Exception as e:
            return {"status": "error", "error": str(e), "timestamp": time.time()}
    
    @health_app.get("/health/live")
    async def liveness_check():
        """Kubernetes liveness probe endpoint."""
        try:
            # Basic liveness check - process is running
            if not shutdown_event.is_set():
                return {"status": "alive", "timestamp": time.time()}
            else:
                return {"status": "dead", "timestamp": time.time()}
        except Exception as e:
            return {"status": "error", "error": str(e), "timestamp": time.time()}
    
    return health_app


async def main_async():
    """Main application entry point with enhanced startup and shutdown handling."""
    global web_server, proxy_manager
    
    logger.info("Starting CLADS LLM Bridge Server...")
    logger.info(f"Configuration: Web UI Port={WEB_UI_PORT}, Proxy Port={PROXY_PORT}, Data Dir={DATA_DIR}")
    
    # Initialize startup manager
    startup_manager = ApplicationStartup()
    
    # Initialize environment
    if not startup_manager.initialize_environment():
        logger.error("Failed to initialize environment")
        sys.exit(1)
    
    # Initialize database
    if not startup_manager.initialize_database():
        logger.error("Failed to initialize database")
        sys.exit(1)
    
    # Load startup configuration
    if not startup_manager.load_startup_configuration():
        logger.error("Failed to load startup configuration")
        sys.exit(1)
    
    # Create FastAPI app with health check endpoints
    web_app = WebApp()
    app = web_app.app
    
    # Add container orchestration health check endpoints to main app
    health_app = create_health_check_app()
    
    # Mount health check routes on main app
    @app.get("/health")
    async def main_health_check():
        """Main application health check."""
        return await health_app.routes[0].endpoint()
    
    @app.get("/health/ready")
    async def main_readiness_check():
        """Main application readiness check."""
        return await health_app.routes[1].endpoint()
    
    @app.get("/health/live")
    async def main_liveness_check():
        """Main application liveness check."""
        return await health_app.routes[2].endpoint()
    
    logger.info(f"Starting servers...")
    logger.info(f"Configuration UI: http://0.0.0.0:{WEB_UI_PORT}")
    logger.info(f"LiteLLM Proxy API: http://0.0.0.0:{PROXY_PORT}")
    logger.info(f"Health Check: http://0.0.0.0:{WEB_UI_PORT}/health")
    
    try:
        # Create web server configuration
        web_config = uvicorn.Config(
            app,
            host="0.0.0.0",
            port=WEB_UI_PORT,
            log_level=LOG_LEVEL.lower(),
            access_log=True
        )
        
        # Create web server instance
        web_server = uvicorn.Server(web_config)
        
        # Start both servers concurrently
        web_task = asyncio.create_task(web_server.serve())
        proxy_task = asyncio.create_task(start_proxy_server_async(startup_manager, PROXY_PORT))
        
        # Create shutdown event task
        shutdown_task = asyncio.create_task(wait_for_shutdown())
        
        logger.info("Both servers starting...")
        
        # Wait for any task to complete or shutdown signal
        done, pending = await asyncio.wait(
            [web_task, proxy_task, shutdown_task],
            return_when=asyncio.FIRST_COMPLETED
        )
        
        logger.info("Shutdown initiated, stopping servers...")
        
        # Cancel pending tasks
        for task in pending:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                logger.info(f"Task {task.get_name()} cancelled successfully")
            except Exception as e:
                logger.error(f"Error cancelling task {task.get_name()}: {e}")
        
        # Graceful shutdown of web server
        if web_server:
            web_server.should_exit = True
        
        # Graceful shutdown of proxy server
        if proxy_manager:
            proxy_manager.shutdown()
        
        logger.info("Application shutdown complete")
        
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt, shutting down...")
    except Exception as e:
        logger.error(f"Error running servers: {e}")
        logger.exception("Full error details:")
        sys.exit(1)


async def wait_for_shutdown():
    """Wait for shutdown event asynchronously."""
    while not shutdown_event.is_set():
        await asyncio.sleep(0.1)


def main():
    """Main entry point - runs the async main function."""
    # Setup signal handlers for graceful shutdown
    setup_signal_handlers()
    
    try:
        # Run the async main function
        asyncio.run(main_async())
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()