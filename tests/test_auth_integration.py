"""Integration tests for authentication system."""

import pytest
import tempfile
import os
from src.auth.authentication_service import AuthenticationService
from src.database.connection import DatabaseConnection
from src.database.migrations import DatabaseMigrations


class TestAuthenticationIntegration:
    """Integration tests for authentication with database."""
    
    @pytest.fixture
    def temp_db_path(self):
        """Create temporary database file."""
        fd, path = tempfile.mkstemp(suffix='.db')
        os.close(fd)
        yield path
        os.unlink(path)
    
    @pytest.fixture
    def initialized_db(self, temp_db_path):
        """Create and initialize database."""
        db_conn = DatabaseConnection(temp_db_path)
        migrations = DatabaseMigrations(db_conn)
        migrations.initialize_database()
        return db_conn
    
    def test_full_authentication_workflow(self, initialized_db):
        """Test complete authentication workflow with database."""
        auth_service = AuthenticationService(initialized_db)
        
        # Initialize default password
        assert auth_service.initialize_default_password() is True
        
        # Test default authentication
        assert auth_service.authenticate("Hakodate4") is True
        assert auth_service.authenticate("wrong") is False
        
        # Test password change
        assert auth_service.change_password("Hakodate4", "new_password123") is True
        
        # Test with new password
        assert auth_service.authenticate("Hakodate4") is False
        assert auth_service.authenticate("new_password123") is True
        
        # Test session management
        session = {}
        assert auth_service.is_authenticated(session) is False
        
        auth_service.set_session_authenticated(session)
        assert auth_service.is_authenticated(session) is True
        assert 'login_time' in session
        
        auth_service.logout(session)
        assert len(session) == 0
    
    def test_auth_config_persistence(self, initialized_db):
        """Test that auth config persists across service instances."""
        # First service instance
        auth_service1 = AuthenticationService(initialized_db)
        auth_service1.initialize_default_password()
        auth_service1.change_password("Hakodate4", "persistent_password")
        
        # Second service instance (simulating restart)
        auth_service2 = AuthenticationService(initialized_db)
        
        # Should authenticate with the changed password
        assert auth_service2.authenticate("persistent_password") is True
        assert auth_service2.authenticate("Hakodate4") is False
    
    def test_database_schema_includes_auth_table(self, initialized_db):
        """Test that auth_config table exists and has correct structure."""
        with initialized_db.get_connection() as conn:
            cursor = conn.cursor()
            
            # Check table exists
            cursor.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='auth_config'
            """)
            assert cursor.fetchone() is not None
            
            # Check table structure
            cursor.execute("PRAGMA table_info(auth_config)")
            columns = {row[1]: row[2] for row in cursor.fetchall()}
            
            expected_columns = {
                'id': 'INTEGER',
                'password_hash': 'TEXT',
                'created_at': 'TIMESTAMP',
                'updated_at': 'TIMESTAMP'
            }
            
            for col_name, col_type in expected_columns.items():
                assert col_name in columns
                assert columns[col_name] == col_type