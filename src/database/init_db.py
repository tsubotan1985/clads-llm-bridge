#!/usr/bin/env python3
"""Database initialization script for CLADS LLM Bridge."""

import logging
import sys
import os
from pathlib import Path

# Add the src directory to the path so we can import our modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from database.connection import DatabaseConnection
from database.migrations import DatabaseMigrations

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def initialize_database(db_path: str = None) -> bool:
    """Initialize the database with enhanced error handling and persistence support.
    
    Args:
        db_path: Optional path to database file
        
    Returns:
        True if initialization successful, False otherwise
    """
    db_connection = None
    
    try:
        logger.info("Starting database initialization...")
        
        # Initialize database connection with optional path
        if db_path:
            db_connection = DatabaseConnection(db_path)
        else:
            db_connection = DatabaseConnection()
        
        # Ensure database directory exists
        db_file_path = Path(db_connection.db_path)
        db_file_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Set appropriate permissions for database directory (skip if permission denied)
        try:
            os.chmod(db_file_path.parent, 0o755)
        except PermissionError:
            # Skip permission setting in test environments or restricted directories
            pass
        
        # Initialize migrations manager
        migrations = DatabaseMigrations(db_connection)
        
        # Check if database exists and has tables
        if db_file_path.exists():
            logger.info(f"Database file exists: {db_file_path}")
            
            # Validate existing schema
            if migrations.validate_schema():
                logger.info("Existing database schema is valid")
                
                # Check if any migrations are needed
                if migrations.needs_migration():
                    logger.info("Database needs migration, applying updates...")
                    migrations.apply_migrations()
                else:
                    logger.info("Database is up to date")
            else:
                logger.warning("Existing database schema is invalid, reinitializing...")
                migrations.initialize_database()
        else:
            logger.info(f"Creating new database: {db_file_path}")
            # Initialize the database
            migrations.initialize_database()
        
        # Final validation
        if migrations.validate_schema():
            logger.info("Database initialization completed successfully")
            
            # Set appropriate permissions for database file
            if db_file_path.exists():
                os.chmod(db_file_path, 0o644)
            
            return True
        else:
            logger.error("Database schema validation failed after initialization")
            return False
            
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        logger.exception("Full error details:")
        return False
    finally:
        if db_connection:
            try:
                db_connection.close()
            except Exception as e:
                logger.warning(f"Error closing database connection: {e}")


def verify_database_health(db_path: str = None) -> bool:
    """Verify database health and connectivity.
    
    Args:
        db_path: Optional path to database file
        
    Returns:
        True if database is healthy, False otherwise
    """
    db_connection = None
    
    try:
        # Initialize database connection
        if db_path:
            db_connection = DatabaseConnection(db_path)
        else:
            db_connection = DatabaseConnection()
        
        # Test basic connectivity
        with db_connection.get_cursor() as cursor:
            cursor.execute("SELECT 1")
            result = cursor.fetchone()
        
        if result and result[0] == 1:
            logger.info("Database connectivity test passed")
            return True
        else:
            logger.error("Database connectivity test failed")
            return False
            
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return False
    finally:
        if db_connection:
            try:
                db_connection.close()
            except Exception as e:
                logger.warning(f"Error closing database connection: {e}")


def get_database_info(db_path: str = None) -> dict:
    """Get database information for startup logging.
    
    Args:
        db_path: Optional path to database file
        
    Returns:
        Dictionary with database information
    """
    db_connection = None
    info = {
        "exists": False,
        "size_bytes": 0,
        "tables": [],
        "version": None,
        "error": None
    }
    
    try:
        # Initialize database connection
        if db_path:
            db_connection = DatabaseConnection(db_path)
        else:
            db_connection = DatabaseConnection()
        
        db_file_path = Path(db_connection.db_path)
        
        # Check if database file exists
        if db_file_path.exists():
            info["exists"] = True
            info["size_bytes"] = db_file_path.stat().st_size
        
        # Get table information
        with db_connection.get_cursor() as cursor:
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = cursor.fetchall()
            info["tables"] = [table[0] for table in tables]
            
            # Get database version if available
            try:
                cursor.execute("PRAGMA user_version")
                version = cursor.fetchone()
                if version:
                    info["version"] = version[0]
            except:
                pass
            
    except Exception as e:
        info["error"] = str(e)
        logger.error(f"Error getting database info: {e}")
    finally:
        if db_connection:
            try:
                db_connection.close()
            except Exception as e:
                logger.warning(f"Error closing database connection: {e}")
    
    return info


def main():
    """Initialize the database from command line."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Initialize CLADS LLM Bridge database")
    parser.add_argument("--db-path", type=str, help="Path to database file")
    parser.add_argument("--verify", action="store_true", help="Verify database health")
    parser.add_argument("--info", action="store_true", help="Show database information")
    
    args = parser.parse_args()
    
    try:
        if args.info:
            # Show database information
            info = get_database_info(args.db_path)
            logger.info(f"Database information: {info}")
            return 0
        elif args.verify:
            # Verify database health
            if verify_database_health(args.db_path):
                logger.info("Database health check passed")
                return 0
            else:
                logger.error("Database health check failed")
                return 1
        else:
            # Initialize database
            if initialize_database(args.db_path):
                logger.info("Database initialization completed successfully")
                return 0
            else:
                logger.error("Database initialization failed")
                return 1
                
    except Exception as e:
        logger.error(f"Command execution failed: {e}")
        return 1


# Convenience function for backward compatibility
def initialize_database_simple():
    """Simple database initialization function for backward compatibility."""
    return initialize_database()


if __name__ == "__main__":
    sys.exit(main())