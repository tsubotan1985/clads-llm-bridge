"""Tests for authentication service."""

import pytest
import tempfile
import os
from datetime import datetime
from unittest.mock import Mock, patch

from src.auth.authentication_service import AuthenticationService
from src.database.connection import DatabaseConnection
from src.database.schema import DatabaseSchema
from src.models.auth import LoginRequest, ChangePasswordRequest


class TestAuthenticationService:
    """Test cases for AuthenticationService."""
    
    @pytest.fixture
    def temp_db(self):
        """Create temporary database for testing."""
        fd, path = tempfile.mkstemp(suffix='.db')
        os.close(fd)
        
        # Initialize database
        db_conn = DatabaseConnection(path)
        with db_conn.get_connection() as conn:
            conn.executescript(DatabaseSchema.get_full_schema_sql())
            conn.commit()
        
        yield db_conn
        
        # Cleanup
        os.unlink(path)
    
    @pytest.fixture
    def auth_service(self, temp_db):
        """Create authentication service with temp database."""
        service = AuthenticationService(temp_db)
        service.initialize_default_password()
        return service
    
    def test_initialize_default_password(self, temp_db):
        """Test default password initialization."""
        service = AuthenticationService(temp_db)
        
        # Should initialize successfully
        assert service.initialize_default_password() is True
        
        # Should authenticate with default password
        assert service.authenticate("Hakodate4") is True
        
        # Should not authenticate with wrong password
        assert service.authenticate("wrong") is False
    
    def test_authenticate_success(self, auth_service):
        """Test successful authentication."""
        assert auth_service.authenticate("Hakodate4") is True
    
    def test_authenticate_failure(self, auth_service):
        """Test failed authentication."""
        assert auth_service.authenticate("wrong_password") is False
        assert auth_service.authenticate("") is False
        assert auth_service.authenticate("hakodate4") is False  # Case sensitive
    
    def test_change_password_success(self, auth_service):
        """Test successful password change."""
        # Change password
        assert auth_service.change_password("Hakodate4", "new_password") is True
        
        # Old password should not work
        assert auth_service.authenticate("Hakodate4") is False
        
        # New password should work
        assert auth_service.authenticate("new_password") is True
    
    def test_change_password_wrong_old_password(self, auth_service):
        """Test password change with wrong old password."""
        assert auth_service.change_password("wrong", "new_password") is False
        
        # Original password should still work
        assert auth_service.authenticate("Hakodate4") is True
    
    def test_is_authenticated_true(self, auth_service):
        """Test session authentication check - authenticated."""
        session = {'authenticated': True}
        assert auth_service.is_authenticated(session) is True
    
    def test_is_authenticated_false(self, auth_service):
        """Test session authentication check - not authenticated."""
        session = {'authenticated': False}
        assert auth_service.is_authenticated(session) is False
        
        session = {}
        assert auth_service.is_authenticated(session) is False
    
    def test_login_success(self, auth_service):
        """Test login with correct password."""
        request = LoginRequest(password="Hakodate4")
        assert auth_service.login(request) is True
    
    def test_login_failure(self, auth_service):
        """Test login with incorrect password."""
        request = LoginRequest(password="wrong")
        assert auth_service.login(request) is False
    
    def test_logout(self, auth_service):
        """Test logout functionality."""
        session = {'authenticated': True, 'user_id': 1}
        auth_service.logout(session)
        assert len(session) == 0
    
    def test_set_session_authenticated(self, auth_service):
        """Test setting session as authenticated."""
        session = {}
        auth_service.set_session_authenticated(session)
        
        assert session['authenticated'] is True
        assert 'login_time' in session
        assert isinstance(session['login_time'], str)
    
    def test_get_auth_config_exists(self, auth_service):
        """Test getting auth config when it exists."""
        config = auth_service._get_auth_config()
        
        assert config is not None
        assert config.id == 1
        assert config.password_hash is not None
        assert len(config.password_hash) > 0
    
    def test_get_auth_config_not_exists(self, temp_db):
        """Test getting auth config when it doesn't exist."""
        service = AuthenticationService(temp_db)
        config = service._get_auth_config()
        
        assert config is None
    
    @patch('src.auth.authentication_service.AuthenticationService._get_auth_config')
    def test_authenticate_database_error(self, mock_get_config, auth_service):
        """Test authentication with database error."""
        mock_get_config.side_effect = Exception("Database error")
        
        assert auth_service.authenticate("Hakodate4") is False
    
    @patch('src.auth.authentication_service.AuthenticationService.authenticate')
    def test_change_password_database_error(self, mock_auth, auth_service):
        """Test password change with database error."""
        mock_auth.return_value = True
        
        with patch.object(auth_service.db, 'get_connection') as mock_conn:
            mock_conn.side_effect = Exception("Database error")
            
            assert auth_service.change_password("Hakodate4", "new") is False