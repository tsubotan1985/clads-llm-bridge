"""Database migration management."""

import logging
from typing import List, Tuple
from .connection import DatabaseConnection
from .schema import DatabaseSchema

logger = logging.getLogger(__name__)


class DatabaseMigrations:
    """Manages database schema migrations."""
    
    def __init__(self, db_connection: DatabaseConnection):
        """Initialize migrations manager.
        
        Args:
            db_connection: Database connection instance
        """
        self.db = db_connection
    
    def get_current_version(self) -> int:
        """Get the current schema version from the database."""
        try:
            result = self.db.execute_query(
                "SELECT MAX(version) as version FROM schema_version"
            )
            if result and result[0]['version'] is not None:
                return result[0]['version']
        except Exception as e:
            logger.warning(f"Could not get schema version: {e}")
        return 0
    
    def set_version(self, version: int) -> None:
        """Set the schema version in the database."""
        self.db.execute_update(
            "INSERT OR REPLACE INTO schema_version (version) VALUES (?)",
            (version,)
        )
        logger.info(f"Schema version set to {version}")
    
    def needs_migration(self) -> bool:
        """Check if database needs migration."""
        current = self.get_current_version()
        target = DatabaseSchema.CURRENT_VERSION
        return current < target
    
    def get_migration_scripts(self) -> List[Tuple[int, str]]:
        """Get list of migration scripts to apply.
        
        Returns:
            List of tuples (version, sql_script)
        """
        migrations = []
        
        # Migration from version 0 to 1 (initial schema)
        if self.get_current_version() < 1:
            migrations.append((1, DatabaseSchema.get_full_schema_sql()))
        
        # Migration from version 1 to 2 (dual endpoint support)
        if self.get_current_version() < 2:
            migrations.append((2, self._get_v2_migration_sql()))
        
        return migrations
    
    def _get_v2_migration_sql(self) -> str:
        """Get SQL for version 2 migration (dual endpoint support).
        
        Returns:
            SQL script for migration
        """
        return """
        -- Add dual endpoint columns to llm_configs table
        ALTER TABLE llm_configs ADD COLUMN available_on_4321 BOOLEAN NOT NULL DEFAULT 1;
        ALTER TABLE llm_configs ADD COLUMN available_on_4333 BOOLEAN NOT NULL DEFAULT 1;
        
        -- Update existing records to be available on both endpoints
        UPDATE llm_configs SET available_on_4321 = 1, available_on_4333 = 1;
        
        -- Update schema version
        INSERT OR REPLACE INTO schema_version (version) VALUES (2);
        """
    
    def apply_migrations(self) -> None:
        """Apply all pending migrations."""
        if not self.needs_migration():
            logger.info("Database is up to date")
            return
        
        current_version = self.get_current_version()
        target_version = DatabaseSchema.CURRENT_VERSION
        
        logger.info(f"Migrating database from version {current_version} to {target_version}")
        
        migrations = self.get_migration_scripts()
        
        for version, sql_script in migrations:
            logger.info(f"Applying migration to version {version}")
            try:
                self.db.execute_script(sql_script)
                self.set_version(version)
                logger.info(f"Successfully applied migration to version {version}")
            except Exception as e:
                logger.error(f"Failed to apply migration to version {version}: {e}")
                raise
        
        logger.info("All migrations applied successfully")
    
    def initialize_database(self) -> None:
        """Initialize the database with the current schema."""
        logger.info("Initializing database")
        
        try:
            # Create the schema_version table first if it doesn't exist
            self.db.execute_script("""
                CREATE TABLE IF NOT EXISTS schema_version (
                    version INTEGER PRIMARY KEY,
                    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            
            # Apply migrations
            self.apply_migrations()
            
            logger.info("Database initialization completed")
            
        except Exception as e:
            logger.error(f"Database initialization failed: {e}")
            raise
    
    def reset_database(self) -> None:
        """Reset the database by dropping all tables and recreating them."""
        logger.warning("Resetting database - all data will be lost!")
        
        # Get list of all tables
        tables = self.db.execute_query("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name NOT LIKE 'sqlite_%'
        """)
        
        # Drop all tables
        for table in tables:
            table_name = table['name']
            self.db.execute_update(f"DROP TABLE IF EXISTS {table_name}")
            logger.info(f"Dropped table: {table_name}")
        
        # Reinitialize
        self.initialize_database()
        logger.info("Database reset completed")
    
    def validate_schema(self) -> bool:
        """Validate that the database schema matches expectations."""
        try:
            # Check that all expected tables exist
            expected_tables = [
                'schema_version', 'llm_configs', 'usage_records', 
                'health_status', 'auth_config'
            ]
            
            existing_tables = self.db.execute_query("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name NOT LIKE 'sqlite_%'
            """)
            
            existing_table_names = {row['name'] for row in existing_tables}
            
            for table in expected_tables:
                if table not in existing_table_names:
                    logger.error(f"Missing table: {table}")
                    return False
            
            # Check schema version
            current_version = self.get_current_version()
            if current_version != DatabaseSchema.CURRENT_VERSION:
                logger.error(f"Schema version mismatch: {current_version} != {DatabaseSchema.CURRENT_VERSION}")
                return False
            
            logger.info("Database schema validation passed")
            return True
            
        except Exception as e:
            logger.error(f"Schema validation failed: {e}")
            return False