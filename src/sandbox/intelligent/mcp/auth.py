"""
Authentication and authorization for the intelligent sandbox MCP server.

This module provides:
- API key-based authentication
- Role-based access control
- Session management
- Request validation and rate limiting
"""

import hashlib
import hmac
import time
import uuid
import logging
from typing import Dict, Any, Optional, Set, List
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
import json

logger = logging.getLogger(__name__)


class Role(Enum):
    """User roles for access control."""
    ADMIN = "admin"
    DEVELOPER = "developer"
    VIEWER = "viewer"


class Permission(Enum):
    """Permissions for sandbox operations."""
    CREATE_WORKSPACE = "create_workspace"
    DELETE_WORKSPACE = "delete_workspace"
    ANALYZE_CODEBASE = "analyze_codebase"
    CREATE_TASK_PLAN = "create_task_plan"
    EXECUTE_TASK_PLAN = "execute_task_plan"
    VIEW_HISTORY = "view_history"
    VIEW_STATUS = "view_status"
    MANAGE_USERS = "manage_users"


@dataclass
class User:
    """User account information."""
    id: str
    username: str
    api_key: str
    role: Role
    permissions: Set[Permission] = field(default_factory=set)
    created_at: float = field(default_factory=time.time)
    last_access: float = field(default_factory=time.time)
    active: bool = True
    rate_limit: int = 100  # requests per hour
    current_requests: int = 0
    rate_limit_reset: float = field(default_factory=time.time)


@dataclass
class Session:
    """User session information."""
    id: str
    user_id: str
    created_at: float = field(default_factory=time.time)
    last_activity: float = field(default_factory=time.time)
    expires_at: float = field(default_factory=lambda: time.time() + 3600)  # 1 hour
    active: bool = True
    workspace_ids: Set[str] = field(default_factory=set)


class AuthenticationManager:
    """Manages user authentication and API key validation."""
    
    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path or "sandbox_auth.json"
        self.users: Dict[str, User] = {}
        self.api_key_to_user: Dict[str, str] = {}
        self.sessions: Dict[str, Session] = {}
        self._load_users()
        self._setup_default_permissions()
    
    def _load_users(self):
        """Load users from configuration file."""
        try:
            config_file = Path(self.config_path)
            if config_file.exists():
                with open(config_file, 'r') as f:
                    data = json.load(f)
                    
                for user_data in data.get('users', []):
                    user = User(
                        id=user_data['id'],
                        username=user_data['username'],
                        api_key=user_data['api_key'],
                        role=Role(user_data['role']),
                        permissions=set(Permission(p) for p in user_data.get('permissions', [])),
                        created_at=user_data.get('created_at', time.time()),
                        last_access=user_data.get('last_access', time.time()),
                        active=user_data.get('active', True),
                        rate_limit=user_data.get('rate_limit', 100)
                    )
                    self.users[user.id] = user
                    self.api_key_to_user[user.api_key] = user.id
                    
                logger.info(f"Loaded {len(self.users)} users from {self.config_path}")
            else:
                # Create default admin user
                self._create_default_admin()
                
        except Exception as e:
            logger.error(f"Failed to load users: {e}")
            self._create_default_admin()
    
    def _create_default_admin(self):
        """Create a default admin user."""
        admin_id = str(uuid.uuid4())
        admin_key = self._generate_api_key()
        
        admin_user = User(
            id=admin_id,
            username="admin",
            api_key=admin_key,
            role=Role.ADMIN,
            permissions=set(Permission)  # All permissions
        )
        
        self.users[admin_id] = admin_user
        self.api_key_to_user[admin_key] = admin_id
        
        # Save to file
        self._save_users()
        
        logger.info(f"Created default admin user with API key: {admin_key}")
    
    def _save_users(self):
        """Save users to configuration file."""
        try:
            data = {
                'users': [
                    {
                        'id': user.id,
                        'username': user.username,
                        'api_key': user.api_key,
                        'role': user.role.value,
                        'permissions': [p.value for p in user.permissions],
                        'created_at': user.created_at,
                        'last_access': user.last_access,
                        'active': user.active,
                        'rate_limit': user.rate_limit
                    }
                    for user in self.users.values()
                ]
            }
            
            with open(self.config_path, 'w') as f:
                json.dump(data, f, indent=2)
                
        except Exception as e:
            logger.error(f"Failed to save users: {e}")
    
    def _generate_api_key(self) -> str:
        """Generate a secure API key."""
        return f"sb_{uuid.uuid4().hex}"
    
    def _setup_default_permissions(self):
        """Set up default permissions for roles."""
        role_permissions = {
            Role.ADMIN: set(Permission),  # All permissions
            Role.DEVELOPER: {
                Permission.CREATE_WORKSPACE,
                Permission.DELETE_WORKSPACE,
                Permission.ANALYZE_CODEBASE,
                Permission.CREATE_TASK_PLAN,
                Permission.EXECUTE_TASK_PLAN,
                Permission.VIEW_HISTORY,
                Permission.VIEW_STATUS
            },
            Role.VIEWER: {
                Permission.VIEW_HISTORY,
                Permission.VIEW_STATUS
            }
        }
        
        # Update users with default permissions if they don't have any
        for user in self.users.values():
            if not user.permissions:
                user.permissions = role_permissions.get(user.role, set())
    
    def authenticate(self, api_key: str) -> Optional[User]:
        """
        Authenticate a user by API key.
        
        Args:
            api_key: The API key to validate
            
        Returns:
            User object if authentication successful, None otherwise
        """
        try:
            user_id = self.api_key_to_user.get(api_key)
            if not user_id:
                logger.warning(f"Authentication failed: Invalid API key")
                return None
            
            user = self.users.get(user_id)
            if not user or not user.active:
                logger.warning(f"Authentication failed: User not found or inactive")
                return None
            
            # Update last access time
            user.last_access = time.time()
            
            # Check rate limiting
            if not self._check_rate_limit(user):
                logger.warning(f"Rate limit exceeded for user {user.username}")
                return None
            
            return user
            
        except Exception as e:
            logger.error(f"Authentication error: {e}")
            return None
    
    def _check_rate_limit(self, user: User) -> bool:
        """Check if user is within rate limits."""
        current_time = time.time()
        
        # Reset rate limit counter if an hour has passed
        if current_time >= user.rate_limit_reset:
            user.current_requests = 0
            user.rate_limit_reset = current_time + 3600  # Next hour
        
        # Check if user has exceeded rate limit
        if user.current_requests >= user.rate_limit:
            return False
        
        # Increment request counter
        user.current_requests += 1
        return True
    
    def create_session(self, user: User) -> Session:
        """
        Create a new session for a user.
        
        Args:
            user: The authenticated user
            
        Returns:
            New session object
        """
        session = Session(
            id=str(uuid.uuid4()),
            user_id=user.id
        )
        
        self.sessions[session.id] = session
        logger.info(f"Created session {session.id} for user {user.username}")
        
        return session
    
    def get_session(self, session_id: str) -> Optional[Session]:
        """
        Get a session by ID.
        
        Args:
            session_id: The session ID
            
        Returns:
            Session object if found and valid, None otherwise
        """
        session = self.sessions.get(session_id)
        if not session or not session.active:
            return None
        
        # Check if session has expired
        if time.time() > session.expires_at:
            session.active = False
            logger.info(f"Session {session_id} expired")
            return None
        
        # Update last activity
        session.last_activity = time.time()
        return session
    
    def cleanup_expired_sessions(self):
        """Remove expired sessions."""
        current_time = time.time()
        expired_sessions = [
            session_id for session_id, session in self.sessions.items()
            if current_time > session.expires_at or not session.active
        ]
        
        for session_id in expired_sessions:
            del self.sessions[session_id]
        
        if expired_sessions:
            logger.info(f"Cleaned up {len(expired_sessions)} expired sessions")


class AuthorizationManager:
    """Manages user authorization and permissions."""
    
    def __init__(self):
        self.operation_permissions = {
            'create_sandbox_workspace': Permission.CREATE_WORKSPACE,
            'analyze_codebase': Permission.ANALYZE_CODEBASE,
            'create_task_plan': Permission.CREATE_TASK_PLAN,
            'execute_task_plan': Permission.EXECUTE_TASK_PLAN,
            'get_execution_history': Permission.VIEW_HISTORY,
            'cleanup_workspace': Permission.DELETE_WORKSPACE,
            'get_sandbox_status': Permission.VIEW_STATUS,
            'manage_users': Permission.MANAGE_USERS
        }
    
    def authorize(self, user: User, operation: str, resource_context: Optional[Dict[str, Any]] = None) -> bool:
        """
        Check if a user is authorized to perform an operation.
        
        Args:
            user: The user to check authorization for
            operation: The operation name
            resource_context: Optional context about the resource being accessed
            
        Returns:
            True if authorized, False otherwise
        """
        try:
            # Check if user is active
            if not user.active:
                logger.warning(f"Authorization denied: User {user.username} is inactive")
                return False
            
            # Get required permission for operation
            required_permission = self.operation_permissions.get(operation)
            if not required_permission:
                logger.warning(f"Unknown operation: {operation}")
                return False
            
            # Check if user has the required permission
            if required_permission not in user.permissions:
                logger.warning(f"Authorization denied: User {user.username} lacks permission {required_permission.value}")
                return False
            
            # Additional resource-based checks
            if resource_context:
                if not self._check_resource_access(user, resource_context):
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"Authorization error: {e}")
            return False
    
    def _check_resource_access(self, user: User, resource_context: Dict[str, Any]) -> bool:
        """Check resource-specific access permissions."""
        # For now, all authenticated users can access their own resources
        # This can be extended for more granular resource-based access control
        
        workspace_id = resource_context.get('workspace_id')
        if workspace_id:
            # Users can only access workspaces they created or have been granted access to
            # For simplicity, we'll allow access to all workspaces for now
            # In a production system, you'd track workspace ownership
            pass
        
        return True


class MCPAuthenticationMiddleware:
    """MCP request authentication and authorization middleware."""
    
    def __init__(self, auth_manager: AuthenticationManager, authz_manager: AuthorizationManager):
        self.auth_manager = auth_manager
        self.authz_manager = authz_manager
    
    def authenticate_request(self, request: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Authenticate an MCP request.
        
        Args:
            request: The MCP request
            
        Returns:
            Authentication context if successful, None otherwise
        """
        try:
            # Extract API key from request headers or parameters
            api_key = self._extract_api_key(request)
            if not api_key:
                return None
            
            # Authenticate user
            user = self.auth_manager.authenticate(api_key)
            if not user:
                return None
            
            # Create or get session
            session = self.auth_manager.create_session(user)
            
            return {
                'user': user,
                'session': session,
                'authenticated': True
            }
            
        except Exception as e:
            logger.error(f"Request authentication error: {e}")
            return None
    
    def authorize_request(self, auth_context: Dict[str, Any], operation: str, 
                         params: Dict[str, Any]) -> bool:
        """
        Authorize an MCP request.
        
        Args:
            auth_context: Authentication context from authenticate_request
            operation: The operation being requested
            params: Request parameters
            
        Returns:
            True if authorized, False otherwise
        """
        try:
            user = auth_context.get('user')
            if not user:
                return False
            
            # Extract resource context from parameters
            resource_context = {
                'workspace_id': params.get('workspace_id'),
                'plan_id': params.get('plan_id')
            }
            
            return self.authz_manager.authorize(user, operation, resource_context)
            
        except Exception as e:
            logger.error(f"Request authorization error: {e}")
            return False
    
    def _extract_api_key(self, request: Dict[str, Any]) -> Optional[str]:
        """Extract API key from MCP request."""
        # Check for API key in different locations
        
        # 1. In request parameters
        params = request.get('params', {})
        if 'api_key' in params:
            return params['api_key']
        
        # 2. In request metadata/headers (if available)
        meta = request.get('meta', {})
        if 'authorization' in meta:
            auth_header = meta['authorization']
            if auth_header.startswith('Bearer '):
                return auth_header[7:]  # Remove 'Bearer ' prefix
        
        # 3. In request context (for stdio transport)
        context = request.get('context', {})
        if 'api_key' in context:
            return context['api_key']
        
        return None
    
    def create_auth_error_response(self, request_id: Any, error_message: str) -> Dict[str, Any]:
        """Create an authentication error response."""
        return {
            "jsonrpc": "1.0",
            "id": request_id,
            "error": {
                "code": -32001,  # Custom authentication error code
                "message": "Authentication failed",
                "data": {
                    "details": error_message,
                    "type": "authentication_error"
                }
            }
        }
    
    def create_authz_error_response(self, request_id: Any, operation: str) -> Dict[str, Any]:
        """Create an authorization error response."""
        return {
            "jsonrpc": "1.0",
            "id": request_id,
            "error": {
                "code": -32002,  # Custom authorization error code
                "message": "Authorization failed",
                "data": {
                    "details": f"Insufficient permissions for operation: {operation}",
                    "type": "authorization_error"
                }
            }
        }


def create_auth_managers(config_path: Optional[str] = None) -> tuple[AuthenticationManager, AuthorizationManager, MCPAuthenticationMiddleware]:
    """
    Create and configure authentication and authorization managers.
    
    Args:
        config_path: Optional path to authentication configuration file
        
    Returns:
        Tuple of (AuthenticationManager, AuthorizationManager, MCPAuthenticationMiddleware)
    """
    auth_manager = AuthenticationManager(config_path)
    authz_manager = AuthorizationManager()
    middleware = MCPAuthenticationMiddleware(auth_manager, authz_manager)
    
    return auth_manager, authz_manager, middleware