"""API Key model for external integrations."""

import secrets
import string
from datetime import datetime, timedelta
from enum import Enum
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, Integer
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID as SQLUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class APIKeyScope(str, Enum):
    """API Key permission scopes."""
    
    WORKFLOW_READ = "workflow:read"
    WORKFLOW_WRITE = "workflow:write"
    WORKFLOW_EXECUTE = "workflow:execute"
    EXECUTION_READ = "execution:read"
    EXECUTION_WRITE = "execution:write"
    AUDIT_READ = "audit:read"
    WEBHOOK_TRIGGER = "webhook:trigger"
    ADMIN = "admin"


class APIKeyStatus(str, Enum):
    """API Key status."""
    
    ACTIVE = "active"
    INACTIVE = "inactive"
    EXPIRED = "expired"
    REVOKED = "revoked"


class APIKey(BaseModel):
    """API Key for external service authentication.
    
    Allows secure access to the API without user credentials.
    Supports granular permissions and expiration.
    """
    
    __tablename__ = "api_keys"
    
    id: Mapped[UUID] = mapped_column(
        SQLUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    organization_id: Mapped[UUID] = mapped_column(
        SQLUUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    created_by: Mapped[UUID | None] = mapped_column(
        SQLUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    
    # Key identifier (public, shown in UI)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    key_prefix: Mapped[str] = mapped_column(String(8), nullable=False, index=True)
    
    # Hashed key (only store hash, never the plain key)
    key_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    
    # Scopes/permissions
    scopes: Mapped[list[str]] = mapped_column(
        ARRAY(String),
        default=list,
        nullable=False,
    )
    
    # Rate limiting
    rate_limit_per_minute: Mapped[int] = mapped_column(Integer, default=60)
    rate_limit_per_hour: Mapped[int] = mapped_column(Integer, default=1000)
    
    # Status and expiration
    status: Mapped[APIKeyStatus] = mapped_column(
        String(20),
        default=APIKeyStatus.ACTIVE,
        nullable=False,
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    
    # Usage tracking
    last_used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    use_count: Mapped[int] = mapped_column(Integer, default=0)
    
    # IP restrictions (optional)
    allowed_ips: Mapped[list[str] | None] = mapped_column(
        ARRAY(String),
        nullable=True,
    )
    
    # Metadata
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    key_metadata: Mapped[dict] = mapped_column(JSONB, default=dict)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    revoked_by: Mapped[UUID | None] = mapped_column(
        SQLUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    
    # Relationships
    organization = relationship("Organization", back_populates="api_keys")
    creator = relationship(
        "User",
        foreign_keys=[created_by],
        back_populates="created_api_keys",
    )
    revoker = relationship(
        "User",
        foreign_keys=[revoked_by],
    )
    usage_logs = relationship(
        "APIKeyUsageLog",
        back_populates="api_key",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )
    
    @staticmethod
    def generate_key() -> tuple[str, str]:
        """Generate a new API key and its prefix.
        
        Returns:
            Tuple of (full_key, key_prefix)
        """
        # Generate 32 character key
        alphabet = string.ascii_letters + string.digits
        key = ''.join(secrets.choice(alphabet) for _ in range(32))
        
        # First 8 chars are the prefix
        prefix = key[:8]
        
        # Format: wfa_xxxxxxxxxxxxxxxxxxxxxxxx (wfa = workflow automation)
        full_key = f"wfa_{key}"
        
        return full_key, prefix
    
    def is_valid(self) -> bool:
        """Check if key is valid for use."""
        if self.status != APIKeyStatus.ACTIVE:
            return False
        
        if self.expires_at and datetime.utcnow() > self.expires_at:
            return False
        
        return True
    
    def has_scope(self, scope: str) -> bool:
        """Check if key has a specific scope."""
        if APIKeyScope.ADMIN.value in self.scopes:
            return True
        return scope in self.scopes
    
    def record_usage(self) -> None:
        """Record key usage."""
        self.last_used_at = datetime.utcnow()
        self.use_count += 1


class APIKeyUsageLog(BaseModel):
    """Log of API key usage.
    
    Tracks all API requests made with API keys for audit and rate limiting.
    """
    
    __tablename__ = "api_key_usage_logs"
    
    id: Mapped[UUID] = mapped_column(
        SQLUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    api_key_id: Mapped[UUID] = mapped_column(
        SQLUUID(as_uuid=True),
        ForeignKey("api_keys.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    organization_id: Mapped[UUID] = mapped_column(
        SQLUUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    # Request details
    endpoint: Mapped[str] = mapped_column(String(500), nullable=False)
    method: Mapped[str] = mapped_column(String(10), nullable=False)
    status_code: Mapped[int] = mapped_column(Integer, nullable=False)
    
    # Client info
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(500), nullable=True)
    
    # Performance
    response_time_ms: Mapped[float | None] = mapped_column(nullable=True)
    
    # Error tracking
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
    )
    
    # Relationships
    api_key = relationship("APIKey", back_populates="usage_logs")
    organization = relationship("Organization", back_populates="api_key_usage_logs")
