"""Tests for authentication middleware."""

import pytest
from unittest.mock import Mock, AsyncMock
from fastapi import Request, HTTPException
from fastapi.responses import RedirectResponse

from src.auth.middleware import AuthMiddleware, require_auth, SessionManager
from src.auth.authentication_service import AuthenticationService


class TestAuthMiddleware:
    """Test cases for AuthMiddleware."""
    
    @pytest.fixture
    def mock_auth_service(self):
        """Create mock authentication service."""
        return Mock(spec=AuthenticationService)
    
    @pytest.fixture
    def auth_middleware(self, mock_auth_service):
        """Create auth middleware with mock service."""
        app = Mock()
        return AuthMiddleware(app, mock_auth_service)
    
    @pytest.fixture
    def mock_request(self):
        """Create mock request."""
        request = Mock(spec=Request)
        request.url = Mock()
        request.session = {}
        return request
    
    def test_is_public_route_exact_match(self, auth_middleware):
        """Test public route detection - exact match."""
        assert auth_middleware._is_public_route('/login') is True
        assert auth_middleware._is_public_route('/health') is True
        assert auth_middleware._is_public_route('/favicon.ico') is True
    
    def test_is_public_route_prefix_match(self, auth_middleware):
        """Test public route detection - prefix match."""
        assert auth_middleware._is_public_route('/static/css/style.css') is True
        assert auth_middleware._is_public_route('/static/js/app.js') is True
    
    def test_is_public_route_private(self, auth_middleware):
        """Test public route detection - private routes."""
        assert auth_middleware._is_public_route('/dashboard') is False
        assert auth_middleware._is_public_route('/config') is False
        assert auth_middleware._is_public_route('/api/models') is False
    
    @pytest.mark.asyncio
    async def test_dispatch_public_route(self, auth_middleware, mock_request):
        """Test middleware dispatch for public routes."""
        mock_request.url.path = '/login'
        call_next = AsyncMock(return_value="response")
        
        result = await auth_middleware.dispatch(mock_request, call_next)
        
        assert result == "response"
        call_next.assert_called_once_with(mock_request)
    
    @pytest.mark.asyncio
    async def test_dispatch_authenticated_user(self, auth_middleware, mock_request, mock_auth_service):
        """Test middleware dispatch for authenticated user."""
        mock_request.url.path = '/dashboard'
        mock_auth_service.is_authenticated.return_value = True
        call_next = AsyncMock(return_value="response")
        
        result = await auth_middleware.dispatch(mock_request, call_next)
        
        assert result == "response"
        call_next.assert_called_once_with(mock_request)
        mock_auth_service.is_authenticated.assert_called_once_with({})
    
    @pytest.mark.asyncio
    async def test_dispatch_unauthenticated_web_route(self, auth_middleware, mock_request, mock_auth_service):
        """Test middleware dispatch for unauthenticated web route."""
        mock_request.url.path = '/dashboard'
        mock_auth_service.is_authenticated.return_value = False
        call_next = AsyncMock()
        
        result = await auth_middleware.dispatch(mock_request, call_next)
        
        assert isinstance(result, RedirectResponse)
        assert result.status_code == 302
        call_next.assert_not_called()


class TestRequireAuthDecorator:
    """Test cases for require_auth decorator."""
    
    @pytest.fixture
    def mock_auth_service(self):
        """Create mock authentication service."""
        return Mock(spec=AuthenticationService)
    
    @pytest.fixture
    def mock_request(self):
        """Create mock request."""
        request = Mock(spec=Request)
        request.session = {}
        return request
    
    @pytest.mark.asyncio
    async def test_require_auth_authenticated(self, mock_auth_service, mock_request):
        """Test require_auth decorator with authenticated user."""
        mock_auth_service.is_authenticated.return_value = True
        
        @require_auth(mock_auth_service)
        async def test_handler(request):
            return "success"
        
        result = await test_handler(mock_request)
        assert result == "success"
    
    @pytest.mark.asyncio
    async def test_require_auth_unauthenticated(self, mock_auth_service, mock_request):
        """Test require_auth decorator with unauthenticated user."""
        mock_auth_service.is_authenticated.return_value = False
        
        @require_auth(mock_auth_service)
        async def test_handler(request):
            return "success"
        
        with pytest.raises(HTTPException) as exc_info:
            await test_handler(mock_request)
        
        assert exc_info.value.status_code == 401
        assert exc_info.value.detail == "Authentication required"


class TestSessionManager:
    """Test cases for SessionManager."""
    
    @pytest.fixture
    def mock_request(self):
        """Create mock request with session."""
        request = Mock(spec=Request)
        request.session = Mock()
        request.session.update = Mock()
        request.session.clear = Mock()
        # Set up session data for get_session_data test
        request.session.__iter__ = Mock(return_value=iter(['key', 'authenticated']))
        request.session.__getitem__ = Mock(side_effect=lambda k: {'key': 'value', 'authenticated': True}[k])
        return request
    
    def test_get_session_data(self):
        """Test getting session data."""
        request = Mock(spec=Request)
        request.session = {'key': 'value', 'authenticated': True}
        
        data = SessionManager.get_session_data(request)
        assert data == {'key': 'value', 'authenticated': True}
    
    def test_get_session_data_no_session(self):
        """Test getting session data when no session exists."""
        request = Mock(spec=Request)
        delattr(request, 'session')
        
        data = SessionManager.get_session_data(request)
        assert data == {}
    
    def test_set_session_data(self):
        """Test setting session data."""
        request = Mock(spec=Request)
        request.session = Mock()
        
        SessionManager.set_session_data(request, {'new_key': 'new_value'})
        
        # Mock update method should be called
        request.session.update.assert_called_once_with({'new_key': 'new_value'})
    
    def test_clear_session(self):
        """Test clearing session."""
        request = Mock(spec=Request)
        request.session = Mock()
        
        SessionManager.clear_session(request)
        
        # Mock clear method should be called
        request.session.clear.assert_called_once()
    
    def test_is_authenticated_true(self):
        """Test is_authenticated with authenticated session."""
        request = Mock(spec=Request)
        request.session = {'authenticated': True}
        
        assert SessionManager.is_authenticated(request) is True
    
    def test_is_authenticated_false(self):
        """Test is_authenticated with unauthenticated session."""
        request = Mock(spec=Request)
        request.session = {'authenticated': False}
        
        assert SessionManager.is_authenticated(request) is False
    
    def test_is_authenticated_no_session(self):
        """Test is_authenticated with no session."""
        request = Mock(spec=Request)
        delattr(request, 'session')
        
        assert SessionManager.is_authenticated(request) is False