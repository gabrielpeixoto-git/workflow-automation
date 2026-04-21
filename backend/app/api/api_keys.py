"""API Key management API routes."""

from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select

from app.core.deps import CurrentUser, DBSession, RequireAdmin
from app.core.logging_config import get_logger
from app.models.api_key import APIKey, APIKeyScope, APIKeyStatus
from app.services.api_key_service import APIKeyService

logger = get_logger(__name__)
router = APIRouter(prefix="/api-keys", tags=["api-keys"])


# Request/Response Schemas

class APIKeyCreateRequest(BaseModel):
    """Create API key request."""
    
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = Field(None, max_length=500)
    scopes: list[str] = Field(
        default=["workflow:read", "execution:read"],
        description="List of permission scopes"
    )
    expires_days: int | None = Field(
        None,
        ge=1,
        le=365,
        description="Days until expiration (null for no expiration)"
    )
    rate_limit_per_minute: int = Field(default=60, ge=1, le=1000)
    rate_limit_per_hour: int = Field(default=1000, ge=1, le=10000)
    allowed_ips: list[str] | None = Field(
        None,
        description="List of allowed IP addresses (null for any)"
    )


class APIKeyUpdateRequest(BaseModel):
    """Update API key request."""
    
    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = Field(None, max_length=500)
    scopes: list[str] | None = None
    status: APIKeyStatus | None = None
    rate_limit_per_minute: int | None = Field(None, ge=1, le=1000)
    rate_limit_per_hour: int | None = Field(None, ge=1, le=10000)


class APIKeyResponse(BaseModel):
    """API key response (without sensitive data)."""
    
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    name: str
    description: str | None
    key_prefix: str
    scopes: list[str]
    status: str
    rate_limit_per_minute: int
    rate_limit_per_hour: int
    use_count: int
    expires_at: datetime | None
    last_used_at: datetime | None
    created_at: datetime
    created_by_email: str | None


class APIKeyCreateResponse(BaseModel):
    """API key create response (includes the plain key - shown only once!)."""
    
    api_key: APIKeyResponse
    key: str = Field(..., description="The API key (shown only once!)")


class APIKeyUsageStats(BaseModel):
    """API key usage statistics."""
    
    total_requests: int
    successful: int
    failed: int
    success_rate: float
    avg_response_time_ms: float
    top_endpoints: list[dict]
    period_days: int


@router.get("", response_model=list[APIKeyResponse])
async def list_api_keys(
    db: DBSession,
    user: CurrentUser,
    status: APIKeyStatus | None = Query(None),
    limit: int = Query(50, ge=1, le=100),
) -> Any:
    """List API keys for the organization.
    
    Returns all API keys without the actual key values.
    """
    keys = await APIKeyService.get_api_keys(
        db=db,
        organization_id=user.organization_id,
        status=status,
        limit=limit,
    )
    
    # Get creator emails
    creator_ids = [k.created_by for k in keys if k.created_by]
    creators = {}
    if creator_ids:
        from app.models.user import User
        result = await db.execute(
            select(User.id, User.email).where(User.id.in_(creator_ids))
        )
        creators = {str(row[0]): row[1] for row in result.all()}
    
    return [
        {
            "id": k.id,
            "name": k.name,
            "description": k.description,
            "key_prefix": k.key_prefix,
            "scopes": k.scopes,
            "status": k.status.value,
            "rate_limit_per_minute": k.rate_limit_per_minute,
            "rate_limit_per_hour": k.rate_limit_per_hour,
            "use_count": k.use_count,
            "expires_at": k.expires_at,
            "last_used_at": k.last_used_at,
            "created_at": k.created_at,
            "created_by_email": creators.get(str(k.created_by), "Sistema"),
        }
        for k in keys
    ]


@router.post("", response_model=APIKeyCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_api_key(
    data: APIKeyCreateRequest,
    db: DBSession,
    user: CurrentUser,
) -> Any:
    """Create a new API key.
    
    **IMPORTANT**: The API key is only returned once in this response.
    Store it securely - it cannot be retrieved again!
    """
    # Validate scopes
    valid_scopes = [s.value for s in APIKeyScope]
    invalid_scopes = [s for s in data.scopes if s not in valid_scopes]
    if invalid_scopes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid scopes: {invalid_scopes}. Valid scopes: {valid_scopes}",
        )
    
    # Check if user can create admin keys
    if APIKeyScope.ADMIN.value in data.scopes and user.role.value != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can create API keys with admin scope",
        )
    
    api_key, plain_key = await APIKeyService.create_api_key(
        db=db,
        user=user,
        name=data.name,
        scopes=data.scopes,
        description=data.description,
        expires_days=data.expires_days,
        rate_limit_per_minute=data.rate_limit_per_minute,
        rate_limit_per_hour=data.rate_limit_per_hour,
        allowed_ips=data.allowed_ips,
    )
    
    return {
        "api_key": {
            "id": api_key.id,
            "name": api_key.name,
            "description": api_key.description,
            "key_prefix": api_key.key_prefix,
            "scopes": api_key.scopes,
            "status": api_key.status.value,
            "rate_limit_per_minute": api_key.rate_limit_per_minute,
            "rate_limit_per_hour": api_key.rate_limit_per_hour,
            "use_count": api_key.use_count,
            "expires_at": api_key.expires_at,
            "last_used_at": api_key.last_used_at,
            "created_at": api_key.created_at,
            "created_by_email": user.email,
        },
        "key": plain_key,
    }


@router.get("/{key_id}", response_model=APIKeyResponse)
async def get_api_key(
    key_id: UUID,
    db: DBSession,
    user: CurrentUser,
) -> Any:
    """Get API key details."""
    api_key = await APIKeyService.get_api_key_by_id(
        db=db,
        key_id=key_id,
        organization_id=user.organization_id,
    )
    
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found",
        )
    
    # Get creator email
    creator_email = "Sistema"
    if api_key.created_by:
        from app.models.user import User
        result = await db.execute(
            select(User.email).where(User.id == api_key.created_by)
        )
        row = result.scalar_one_or_none()
        if row:
            creator_email = row
    
    return {
        "id": api_key.id,
        "name": api_key.name,
        "description": api_key.description,
        "key_prefix": api_key.key_prefix,
        "scopes": api_key.scopes,
        "status": api_key.status.value,
        "rate_limit_per_minute": api_key.rate_limit_per_minute,
        "rate_limit_per_hour": api_key.rate_limit_per_hour,
        "use_count": api_key.use_count,
        "expires_at": api_key.expires_at,
        "last_used_at": api_key.last_used_at,
        "created_at": api_key.created_at,
        "created_by_email": creator_email,
    }


@router.put("/{key_id}", response_model=APIKeyResponse)
async def update_api_key(
    key_id: UUID,
    data: APIKeyUpdateRequest,
    db: DBSession,
    user: CurrentUser,
) -> Any:
    """Update API key."""
    api_key = await APIKeyService.get_api_key_by_id(
        db=db,
        key_id=key_id,
        organization_id=user.organization_id,
    )
    
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found",
        )
    
    # Validate scopes if provided
    if data.scopes:
        valid_scopes = [s.value for s in APIKeyScope]
        invalid_scopes = [s for s in data.scopes if s not in valid_scopes]
        if invalid_scopes:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid scopes: {invalid_scopes}",
            )
        
        # Check admin scope
        if APIKeyScope.ADMIN.value in data.scopes and user.role.value != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only admins can add admin scope",
            )
    
    updated = await APIKeyService.update_api_key(
        db=db,
        api_key=api_key,
        name=data.name,
        scopes=data.scopes,
        description=data.description,
        status=data.status,
        rate_limit_per_minute=data.rate_limit_per_minute,
        rate_limit_per_hour=data.rate_limit_per_hour,
    )
    
    return {
        "id": updated.id,
        "name": updated.name,
        "description": updated.description,
        "key_prefix": updated.key_prefix,
        "scopes": updated.scopes,
        "status": updated.status.value,
        "rate_limit_per_minute": updated.rate_limit_per_minute,
        "rate_limit_per_hour": updated.rate_limit_per_hour,
        "use_count": updated.use_count,
        "expires_at": updated.expires_at,
        "last_used_at": updated.last_used_at,
        "created_at": updated.created_at,
        "created_by_email": user.email,
    }


@router.post("/{key_id}/revoke")
async def revoke_api_key(
    key_id: UUID,
    db: DBSession,
    user: CurrentUser,
) -> dict:
    """Revoke an API key.
    
    Revoked keys cannot be used but remain in the list for audit purposes.
    """
    api_key = await APIKeyService.get_api_key_by_id(
        db=db,
        key_id=key_id,
        organization_id=user.organization_id,
    )
    
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found",
        )
    
    if api_key.status == APIKeyStatus.REVOKED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="API key is already revoked",
        )
    
    await APIKeyService.revoke_api_key(db, api_key, user)
    
    return {"message": "API key revoked successfully"}


@router.get("/{key_id}/stats", response_model=APIKeyUsageStats)
async def get_api_key_stats(
    key_id: UUID,
    db: DBSession,
    user: CurrentUser,
    days: int = Query(7, ge=1, le=30),
) -> Any:
    """Get usage statistics for an API key."""
    api_key = await APIKeyService.get_api_key_by_id(
        db=db,
        key_id=key_id,
        organization_id=user.organization_id,
    )
    
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found",
        )
    
    stats = await APIKeyService.get_usage_stats(db, key_id, days)
    return stats


@router.get("/scopes/list")
async def list_available_scopes(
    user: CurrentUser,
) -> Any:
    """List all available API key scopes."""
    scopes = [
        {
            "value": s.value,
            "label": s.value.replace(":", " ").title(),
            "category": s.value.split(":")[0],
        }
        for s in APIKeyScope
    ]
    
    # Group by category
    categories = {}
    for scope in scopes:
        cat = scope["category"]
        if cat not in categories:
            categories[cat] = []
        categories[cat].append(scope)
    
    return {
        "scopes": scopes,
        "by_category": categories,
    }
