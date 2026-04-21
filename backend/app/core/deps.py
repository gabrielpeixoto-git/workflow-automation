"""FastAPI dependencies."""

from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging_config import get_logger
from app.core.rbac import Permission, RBAC
from app.core.security import decode_token
from app.db.database import AsyncSessionLocal
from app.models.user import User, UserRole

logger = get_logger(__name__)
security = HTTPBearer(auto_error=False)


def get_client_info(request: Request) -> tuple[str | None, str | None]:
    """Get client IP and user agent from request."""
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        ip_address = forwarded_for.split(",")[0].strip()
    elif request.client:
        ip_address = request.client.host
    else:
        ip_address = None
    user_agent = request.headers.get("user-agent")
    return ip_address, user_agent


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Get database session dependency."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


DBSession = Annotated[AsyncSession, Depends(get_db)]


async def get_current_user(
    request: Request,
    db: DBSession,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security)] = None,
) -> User:
    """Get current authenticated user from JWT token."""
    # Try to get token from Authorization header
    token = None
    if credentials:
        token = credentials.credentials
    else:
        # Try to get from cookie
        token = request.cookies.get("access_token")
    
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    payload = decode_token(token)
    if not payload or payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    import uuid
    result = await db.execute(
        select(User).where(
            User.id == uuid.UUID(user_id),
            User.is_active == True,
            User.deleted_at.is_(None),
        )
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


async def require_admin(user: CurrentUser) -> User:
    """Require admin role."""
    if not user.is_superuser and user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return user


RequireAdmin = Annotated[User, Depends(require_admin)]


async def require_editor(user: CurrentUser) -> User:
    """Require editor or admin role."""
    if not user.is_superuser and user.role not in (UserRole.ADMIN, UserRole.EDITOR):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Editor access required",
        )
    return user


RequireEditor = Annotated[User, Depends(require_editor)]


async def get_optional_user(
    request: Request,
    db: DBSession,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security)] = None,
) -> User | None:
    """Get optional current user (returns None if not authenticated)."""
    try:
        return await get_current_user(request, db, credentials)
    except HTTPException:
        return None


OptionalUser = Annotated[User | None, Depends(get_optional_user)]


# RBAC Permission Dependencies

async def require_permission(
    permission: Permission,
    user: CurrentUser,
) -> User:
    """Require specific permission."""
    if not RBAC.has_permission(user, permission):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Permission denied: {permission.value} required",
        )
    return user


def check_permission_factory(permission: Permission):
    """Factory to create permission check dependencies."""
    async def _check(user: CurrentUser) -> User:
        if not RBAC.has_permission(user, permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied: {permission.value} required",
            )
        return user
    return _check


# Pre-defined permission dependencies
RequireWorkflowView = Annotated[User, Depends(check_permission_factory(Permission.WORKFLOW_VIEW))]
RequireWorkflowCreate = Annotated[User, Depends(check_permission_factory(Permission.WORKFLOW_CREATE))]
RequireWorkflowEdit = Annotated[User, Depends(check_permission_factory(Permission.WORKFLOW_EDIT))]
RequireWorkflowDelete = Annotated[User, Depends(check_permission_factory(Permission.WORKFLOW_DELETE))]
RequireWorkflowActivate = Annotated[User, Depends(check_permission_factory(Permission.WORKFLOW_ACTIVATE))]

RequireExecutionView = Annotated[User, Depends(check_permission_factory(Permission.EXECUTION_VIEW))]
RequireExecutionStart = Annotated[User, Depends(check_permission_factory(Permission.EXECUTION_START))]
RequireExecutionCancel = Annotated[User, Depends(check_permission_factory(Permission.EXECUTION_CANCEL))]
RequireExecutionRetry = Annotated[User, Depends(check_permission_factory(Permission.EXECUTION_RETRY))]

RequireUserView = Annotated[User, Depends(check_permission_factory(Permission.USER_VIEW))]
RequireUserCreate = Annotated[User, Depends(check_permission_factory(Permission.USER_CREATE))]
RequireUserEdit = Annotated[User, Depends(check_permission_factory(Permission.USER_EDIT))]
RequireUserDelete = Annotated[User, Depends(check_permission_factory(Permission.USER_DELETE))]

RequireAuditView = Annotated[User, Depends(check_permission_factory(Permission.AUDIT_VIEW))]
RequireNotificationView = Annotated[User, Depends(check_permission_factory(Permission.NOTIFICATION_VIEW))]
RequireNotificationConfig = Annotated[User, Depends(check_permission_factory(Permission.NOTIFICATION_CONFIG))]
