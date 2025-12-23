"""Authentication service for web UI."""

from passlib.context import CryptContext
import sqlite3
from datetime import datetime
from typing import Optional
from ..database.connection import DatabaseConnection
from ..models.auth import AuthConfig, LoginRequest, ChangePasswordRequest


class AuthenticationService:
    """Service for handling authentication operations."""
    
    def __init__(self, db_connection: DatabaseConnection):
        """Initialize authentication service.
        
        Args:
            db_connection: Database connection instance
        """
        self.db = db_connection
        self.pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    
    def authenticate(self, password: str) -> bool:
        """Authenticate user with password.
        
        Args:
            password: Plain text password to verify
            
        Returns:
            True if authentication successful, False otherwise
        """
        try:
            auth_config = self._get_auth_config()
            if not auth_config:
                return False
            
            # Check if it's a SHA256 hash (temporary workaround for bcrypt issues)
            if auth_config.password_hash and auth_config.password_hash.startswith('sha256_'):
                parts = auth_config.password_hash.split('_')
                if len(parts) == 3:
                    _, salt, stored_hash = parts
                    import hashlib
                    password_with_salt = password + salt
                    calculated_hash = hashlib.sha256(password_with_salt.encode()).hexdigest()
                    return calculated_hash == stored_hash
                return False
            
            # Verify password against stored bcrypt hash
            try:
                return self.pwd_context.verify(password, auth_config.password_hash)
            except Exception as bcrypt_error:
                print(f"Bcrypt verification failed: {bcrypt_error}")
                return False
        except Exception as e:
            print(f"Authentication error: {e}")
            return False
    
    def change_password(self, old_password: str, new_password: str) -> bool:
        """Change user password.
        
        Args:
            old_password: Current password for verification
            new_password: New password to set
            
        Returns:
            True if password changed successfully, False otherwise
        """
        try:
            # First verify old password
            if not self.authenticate(old_password):
                return False
            
            # Hash new password
            new_hash = self.pwd_context.hash(new_password)
            
            # Update password in database
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE auth_config 
                    SET password_hash = ?, updated_at = ?
                    WHERE id = 1
                """, (new_hash, datetime.utcnow().isoformat()))
                conn.commit()
                
                return cursor.rowcount > 0
                
        except Exception as e:
            print(f"Password change error: {e}")
            return False
    
    def is_authenticated(self, session_data: dict) -> bool:
        """Check if session is authenticated.
        
        Args:
            session_data: Session data dictionary
            
        Returns:
            True if session is authenticated, False otherwise
        """
        return session_data.get('authenticated', False) is True
    
    def login(self, request: LoginRequest) -> bool:
        """Login user and return success status.
        
        Args:
            request: Login request with password
            
        Returns:
            True if login successful, False otherwise
        """
        return self.authenticate(request.password)
    
    def logout(self, session_data: dict) -> None:
        """Logout user by clearing session.
        
        Args:
            session_data: Session data dictionary to clear
        """
        session_data.clear()
    
    def set_session_authenticated(self, session_data: dict) -> None:
        """Mark session as authenticated.
        
        Args:
            session_data: Session data dictionary to update
        """
        session_data['authenticated'] = True
        session_data['login_time'] = datetime.utcnow().isoformat()
    
    def _get_auth_config(self) -> Optional[AuthConfig]:
        """Get authentication configuration from database.
        
        Returns:
            AuthConfig instance or None if not found
        """
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT id, password_hash, created_at, updated_at
                    FROM auth_config
                    WHERE id = 1
                """)
                row = cursor.fetchone()
                
                if row:
                    return AuthConfig.from_dict({
                        'id': row[0],
                        'password_hash': row[1],
                        'created_at': row[2],
                        'updated_at': row[3]
                    })
                return None
                
        except Exception as e:
            print(f"Error getting auth config: {e}")
            return None
    
    def initialize_default_password(self) -> bool:
        """Initialize default password if not exists.
        
        Returns:
            True if initialization successful, False otherwise
        """
        try:
            # Check if auth config already exists
            if self._get_auth_config():
                return True
            
            # Hash default password "Hakodate4"
            default_hash = self.pwd_context.hash("Hakodate4")
            
            # Insert default auth config
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR IGNORE INTO auth_config (id, password_hash)
                    VALUES (1, ?)
                """, (default_hash,))
                conn.commit()
                
                return True
                
        except Exception as e:
            print(f"Error initializing default password: {e}")
            return False