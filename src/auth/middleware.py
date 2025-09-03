"""Authentication middleware for FastAPI."""

from typing import Callable, Optional
from fastapi import Request, Response, HTTPException
from fastapi.responses import RedirectResponse
from starlette.middleware.base import BaseHTTPMiddleware
from .authentication_service import AuthenticationService


class AuthMiddleware(BaseHTTPMiddleware):
    """Middleware to handle authentication for protected routes."""
    
    def __init__(self, app, auth_service: AuthenticationService):
        """Initialize authentication middleware.
        
        Args:
            app: FastAPI application instance
            auth_service: Authentication service instance
        """
        super().__init__(app)
        self.auth_service = auth_service
        
        # Routes that don't require authentication
        self.public_routes = {
            '/login',
            '/static',
            '/favicon.ico',
            '/health'
        }
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request through authentication middleware.
        
        Args:
            request: Incoming HTTP request
            call_next: Next middleware/handler in chain
            
        Returns:
            HTTP response
        """
        # Check if route requires authentication
        if self._is_public_route(request.url.path):
            return await call_next(request)
        
        # Check if user is authenticated
        try:
            session = request.session
        except (AttributeError, AssertionError):
            # SessionMiddleware not properly configured or session not available
            session = {}
        
        if not self.auth_service.is_authenticated(session):
            # Redirect to login page for web UI routes
            if request.url.path.startswith('/'):
                return RedirectResponse(url='/login', status_code=302)
            else:
                # Return 401 for API routes
                raise HTTPException(status_code=401, detail="Authentication required")
        
        # User is authenticated, proceed with request
        return await call_next(request)
    
    def _is_public_route(self, path: str) -> bool:
        """Check if route is public (doesn't require authentication).
        
        Args:
            path: Request path
            
        Returns:
            True if route is public, False otherwise
        """
        # Check exact matches
        if path in self.public_routes:
            return True
        
        # Check prefix matches for static files
        for public_route in self.public_routes:
            if path.startswith(public_route + '/'):
                return True
        
        return False


def require_auth(auth_service: AuthenticationService):
    """Decorator to require authentication for route handlers.
    
    Args:
        auth_service: Authentication service instance
        
    Returns:
        Decorator function
    """
    def decorator(func):
        async def wrapper(request: Request, *args, **kwargs):
            try:
                session = request.session
            except (AttributeError, AssertionError):
                session = {}
            
            if not auth_service.is_authenticated(session):
                raise HTTPException(status_code=401, detail="Authentication required")
            
            return await func(request, *args, **kwargs)
        
        return wrapper
    return decorator


class SessionManager:
    """Helper class for managing user sessions."""
    
    @staticmethod
    def get_session_data(request: Request) -> dict:
        """Get session data from request.
        
        Args:
            request: HTTP request object
            
        Returns:
            Session data dictionary
        """
        try:
            return dict(request.session)
        except (AttributeError, AssertionError):
            return {}
    
    @staticmethod
    def set_session_data(request: Request, data: dict) -> None:
        """Set session data in request.
        
        Args:
            request: HTTP request object
            data: Data to store in session
        """
        try:
            request.session.update(data)
        except (AttributeError, AssertionError):
            pass  # Session not available
    
    @staticmethod
    def clear_session(request: Request) -> None:
        """Clear session data.
        
        Args:
            request: HTTP request object
        """
        try:
            request.session.clear()
        except (AttributeError, AssertionError):
            pass  # Session not available
    
    @staticmethod
    def is_authenticated(request: Request) -> bool:
        """Check if current session is authenticated.
        
        Args:
            request: HTTP request object
            
        Returns:
            True if authenticated, False otherwise
        """
        session = SessionManager.get_session_data(request)
        return session.get('authenticated', False) is True