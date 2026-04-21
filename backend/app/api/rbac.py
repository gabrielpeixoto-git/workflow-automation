"""RBAC management API routes."""

from typing import Any

from fastapi import APIRouter, status
from pydantic import BaseModel, ConfigDict

from app.core.deps import CurrentUser, RequireAdmin
from app.core.rbac import (
    Permission,
    ROLE_PERMISSIONS,
    PERMISSION_DESCRIPTIONS,
    get_role_permissions,
    get_user_permissions_summary,
)
from app.models.user import User, UserRole

router = APIRouter(prefix="/rbac", tags=["rbac"])


class RoleInfo(BaseModel):
    """Role information."""
    
    model_config = ConfigDict(from_attributes=True)
    
    value: str
    label: str
    description: str


class PermissionInfo(BaseModel):
    """Permission information."""
    
    model_config = ConfigDict(from_attributes=True)
    
    permission: str
    description: str
    category: str


class RolePermissionsResponse(BaseModel):
    """Role permissions response."""
    
    model_config = ConfigDict(from_attributes=True)
    
    role: str
    permissions: list[PermissionInfo]
    permissions_count: int


class UserPermissionsResponse(BaseModel):
    """User permissions summary response."""
    
    model_config = ConfigDict(from_attributes=True)
    
    role: str
    is_admin: bool
    is_editor: bool
    is_superuser: bool
    permissions_count: int
    permissions: list[str]


class AllRolesResponse(BaseModel):
    """All roles and permissions response."""
    
    model_config = ConfigDict(from_attributes=True)
    
    roles: list[RoleInfo]
    permissions_by_role: dict[str, list[PermissionInfo]]


@router.get("/roles", response_model=list[RoleInfo])
async def list_roles(
    user: CurrentUser,
) -> Any:
    """List all available roles.
    
    Returns all system roles with their labels and descriptions.
    """
    roles = [
        {
            "value": UserRole.ADMIN.value,
            "label": "Administrador",
            "description": "Acesso total ao sistema. Pode gerenciar workflows, usuários e configurações da organização.",
        },
        {
            "value": UserRole.EDITOR.value,
            "label": "Editor",
            "description": "Pode criar e editar workflows, executar tarefas e visualizar logs. Não pode gerenciar usuários.",
        },
        {
            "value": UserRole.VIEWER.value,
            "label": "Visualizador",
            "description": "Apenas visualização. Pode ver workflows e execuções, mas não pode modificá-los.",
        },
    ]
    return roles


@router.get("/roles/{role}/permissions", response_model=RolePermissionsResponse)
async def get_role_permissions_endpoint(
    role: UserRole,
    user: CurrentUser,
) -> Any:
    """Get permissions for a specific role.
    
    Returns all permissions assigned to the specified role.
    """
    permissions = get_role_permissions(role)
    
    return {
        "role": role.value,
        "permissions": permissions,
        "permissions_count": len(permissions),
    }


@router.get("/permissions", response_model=AllRolesResponse)
async def get_all_permissions(
    user: RequireAdmin,
) -> Any:
    """Get all roles and their permissions.
    
    **Admin only** - Returns complete RBAC configuration for all roles.
    """
    roles = [
        {
            "value": UserRole.ADMIN.value,
            "label": "Administrador",
            "description": "Acesso total ao sistema.",
        },
        {
            "value": UserRole.EDITOR.value,
            "label": "Editor",
            "description": "Pode criar e editar workflows.",
        },
        {
            "value": UserRole.VIEWER.value,
            "label": "Visualizador",
            "description": "Apenas visualização.",
        },
    ]
    
    permissions_by_role = {
        role.value: get_role_permissions(role)
        for role in UserRole
    }
    
    return {
        "roles": roles,
        "permissions_by_role": permissions_by_role,
    }


@router.get("/my-permissions", response_model=UserPermissionsResponse)
async def get_my_permissions(
    user: CurrentUser,
) -> Any:
    """Get current user's permissions summary.
    
    Returns the current user's role and all their permissions.
    """
    return get_user_permissions_summary(user)


@router.get("/permission-categories")
async def get_permission_categories(
    user: CurrentUser,
) -> Any:
    """Get permissions grouped by category.
    
    Categories: workflow, execution, user, org, audit, notification
    """
    categories = {
        "workflow": {
            "label": "Workflows",
            "icon": "diagram-3",
            "permissions": [
                {"value": p.value, "description": PERMISSION_DESCRIPTIONS.get(p, p.value)}
                for p in Permission if p.value.startswith("workflow:")
            ],
        },
        "execution": {
            "label": "Execuções",
            "icon": "play-circle",
            "permissions": [
                {"value": p.value, "description": PERMISSION_DESCRIPTIONS.get(p, p.value)}
                for p in Permission if p.value.startswith("execution:")
            ],
        },
        "user": {
            "label": "Usuários",
            "icon": "people",
            "permissions": [
                {"value": p.value, "description": PERMISSION_DESCRIPTIONS.get(p, p.value)}
                for p in Permission if p.value.startswith("user:")
            ],
        },
        "org": {
            "label": "Organização",
            "icon": "building",
            "permissions": [
                {"value": p.value, "description": PERMISSION_DESCRIPTIONS.get(p, p.value)}
                for p in Permission if p.value.startswith("org:")
            ],
        },
        "audit": {
            "label": "Auditoria",
            "icon": "journal-text",
            "permissions": [
                {"value": p.value, "description": PERMISSION_DESCRIPTIONS.get(p, p.value)}
                for p in Permission if p.value.startswith("audit:")
            ],
        },
        "notification": {
            "label": "Notificações",
            "icon": "bell",
            "permissions": [
                {"value": p.value, "description": PERMISSION_DESCRIPTIONS.get(p, p.value)}
                for p in Permission if p.value.startswith("notification:")
            ],
        },
    }
    
    return categories
