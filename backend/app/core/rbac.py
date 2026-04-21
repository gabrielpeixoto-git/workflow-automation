"""RBAC (Role-Based Access Control) implementation."""

from enum import Enum
from functools import wraps
from typing import Callable

from fastapi import HTTPException, status

from app.models.user import User, UserRole


class Permission(str, Enum):
    """Granular permissions."""
    
    # Workflow permissions
    WORKFLOW_VIEW = "workflow:view"
    WORKFLOW_CREATE = "workflow:create"
    WORKFLOW_EDIT = "workflow:edit"
    WORKFLOW_DELETE = "workflow:delete"
    WORKFLOW_ACTIVATE = "workflow:activate"
    
    # Execution permissions
    EXECUTION_VIEW = "execution:view"
    EXECUTION_START = "execution:start"
    EXECUTION_CANCEL = "execution:cancel"
    EXECUTION_RETRY = "execution:retry"
    
    # User management
    USER_VIEW = "user:view"
    USER_CREATE = "user:create"
    USER_EDIT = "user:edit"
    USER_DELETE = "user:delete"
    
    # Organization management
    ORG_VIEW = "org:view"
    ORG_EDIT = "org:edit"
    ORG_SETTINGS = "org:settings"
    
    # Audit logs
    AUDIT_VIEW = "audit:view"
    
    # Notifications
    NOTIFICATION_VIEW = "notification:view"
    NOTIFICATION_CONFIG = "notification:config"


# Role-based permission mapping
ROLE_PERMISSIONS: dict[UserRole, list[Permission]] = {
    UserRole.ADMIN: [
        # Admin has all permissions
        Permission.WORKFLOW_VIEW,
        Permission.WORKFLOW_CREATE,
        Permission.WORKFLOW_EDIT,
        Permission.WORKFLOW_DELETE,
        Permission.WORKFLOW_ACTIVATE,
        Permission.EXECUTION_VIEW,
        Permission.EXECUTION_START,
        Permission.EXECUTION_CANCEL,
        Permission.EXECUTION_RETRY,
        Permission.USER_VIEW,
        Permission.USER_CREATE,
        Permission.USER_EDIT,
        Permission.USER_DELETE,
        Permission.ORG_VIEW,
        Permission.ORG_EDIT,
        Permission.ORG_SETTINGS,
        Permission.AUDIT_VIEW,
        Permission.NOTIFICATION_VIEW,
        Permission.NOTIFICATION_CONFIG,
    ],
    UserRole.EDITOR: [
        # Editor can manage workflows and executions
        Permission.WORKFLOW_VIEW,
        Permission.WORKFLOW_CREATE,
        Permission.WORKFLOW_EDIT,
        Permission.WORKFLOW_ACTIVATE,
        Permission.EXECUTION_VIEW,
        Permission.EXECUTION_START,
        Permission.EXECUTION_CANCEL,
        Permission.EXECUTION_RETRY,
        Permission.USER_VIEW,
        Permission.ORG_VIEW,
        Permission.AUDIT_VIEW,
        Permission.NOTIFICATION_VIEW,
        Permission.NOTIFICATION_CONFIG,
    ],
    UserRole.VIEWER: [
        # Viewer can only view
        Permission.WORKFLOW_VIEW,
        Permission.EXECUTION_VIEW,
        Permission.USER_VIEW,
        Permission.ORG_VIEW,
        Permission.AUDIT_VIEW,
        Permission.NOTIFICATION_VIEW,
    ],
}


class RBAC:
    """Role-Based Access Control helper class."""
    
    @staticmethod
    def has_permission(user: User, permission: Permission) -> bool:
        """Check if user has a specific permission."""
        if not user or not user.is_active:
            return False
        
        # Superusers have all permissions
        if user.is_superuser:
            return True
        
        # Get permissions for user's role
        user_permissions = ROLE_PERMISSIONS.get(user.role, [])
        return permission in user_permissions
    
    @staticmethod
    def has_any_permission(user: User, permissions: list[Permission]) -> bool:
        """Check if user has any of the specified permissions."""
        return any(RBAC.has_permission(user, p) for p in permissions)
    
    @staticmethod
    def has_all_permissions(user: User, permissions: list[Permission]) -> bool:
        """Check if user has all specified permissions."""
        return all(RBAC.has_permission(user, p) for p in permissions)
    
    @staticmethod
    def require_permission(permission: Permission):
        """Decorator to require a specific permission."""
        def decorator(func: Callable) -> Callable:
            @wraps(func)
            async def wrapper(*args, **kwargs):
                # Extract user from kwargs or args
                user = kwargs.get('user') or kwargs.get('current_user')
                if not user:
                    for arg in args:
                        if isinstance(arg, User):
                            user = arg
                            break
                
                if not user or not RBAC.has_permission(user, permission):
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=f"Permission denied: {permission.value} required",
                    )
                
                return await func(*args, **kwargs)
            return wrapper
        return decorator


# Permission check functions for dependencies
def check_permission(user: User, permission: Permission) -> None:
    """Check permission and raise HTTPException if denied."""
    if not RBAC.has_permission(user, permission):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Permission denied: {permission.value} required",
        )


def require_admin(user: User) -> None:
    """Require admin role."""
    if not user or user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required",
        )


def require_editor_or_admin(user: User) -> None:
    """Require editor or admin role."""
    if not user or user.role not in (UserRole.ADMIN, UserRole.EDITOR):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Editor or Admin role required",
        )


# Permission descriptions for UI
PERMISSION_DESCRIPTIONS: dict[Permission, str] = {
    Permission.WORKFLOW_VIEW: "Visualizar workflows",
    Permission.WORKFLOW_CREATE: "Criar workflows",
    Permission.WORKFLOW_EDIT: "Editar workflows",
    Permission.WORKFLOW_DELETE: "Excluir workflows",
    Permission.WORKFLOW_ACTIVATE: "Ativar/desativar workflows",
    Permission.EXECUTION_VIEW: "Visualizar execuções",
    Permission.EXECUTION_START: "Iniciar execuções",
    Permission.EXECUTION_CANCEL: "Cancelar execuções",
    Permission.EXECUTION_RETRY: "Retry de execuções",
    Permission.USER_VIEW: "Visualizar usuários",
    Permission.USER_CREATE: "Criar usuários",
    Permission.USER_EDIT: "Editar usuários",
    Permission.USER_DELETE: "Excluir usuários",
    Permission.ORG_VIEW: "Visualizar organização",
    Permission.ORG_EDIT: "Editar organização",
    Permission.ORG_SETTINGS: "Configurações da organização",
    Permission.AUDIT_VIEW: "Visualizar logs de auditoria",
    Permission.NOTIFICATION_VIEW: "Visualizar notificações",
    Permission.NOTIFICATION_CONFIG: "Configurar notificações",
}


def get_role_permissions(role: UserRole) -> list[dict]:
    """Get all permissions for a role with descriptions."""
    permissions = ROLE_PERMISSIONS.get(role, [])
    return [
        {
            "permission": p.value,
            "description": PERMISSION_DESCRIPTIONS.get(p, p.value),
            "category": p.value.split(":")[0],
        }
        for p in permissions
    ]


def get_user_permissions_summary(user: User) -> dict:
    """Get permission summary for a user."""
    if not user:
        return {"role": None, "permissions": []}
    
    all_permissions = ROLE_PERMISSIONS.get(user.role, [])
    
    return {
        "role": user.role.value,
        "is_admin": user.role == UserRole.ADMIN,
        "is_editor": user.role in (UserRole.ADMIN, UserRole.EDITOR),
        "is_superuser": user.is_superuser,
        "permissions_count": len(all_permissions),
        "permissions": [p.value for p in all_permissions],
    }
