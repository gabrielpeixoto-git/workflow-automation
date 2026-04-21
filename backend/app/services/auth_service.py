"""Authentication service."""

import uuid
from datetime import timedelta

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging_config import get_logger
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    get_password_hash,
    verify_password,
)
from app.models.audit_log import AuditAction, AuditLog
from app.models.organization import Organization
from app.models.user import User, UserRole

logger = get_logger(__name__)


class AuthService:
    """Authentication service."""

    @staticmethod
    async def register_user(
        db: AsyncSession,
        email: str,
        password: str,
        full_name: str | None,
        organization_name: str,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> User:
        """Register a new user with organization."""
        # Check if email already exists
        result = await db.execute(select(User).where(User.email == email))
        if result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered",
            )

        # Create organization
        import re
        org_slug = re.sub(r'[^\w\s-]', '', organization_name).strip().lower()
        org_slug = re.sub(r'[-\s]+', '-', org_slug)

        # Ensure unique slug
        base_slug = org_slug
        counter = 1
        while True:
            result = await db.execute(
                select(Organization).where(Organization.slug == org_slug)
            )
            if not result.scalar_one_or_none():
                break
            org_slug = f"{base_slug}-{counter}"
            counter += 1

        org = Organization(
            name=organization_name,
            slug=org_slug,
        )
        db.add(org)
        await db.flush()

        # Create user as admin
        user = User(
            email=email,
            hashed_password=get_password_hash(password),
            full_name=full_name,
            role=UserRole.ADMIN,
            organization_id=org.id,
        )
        db.add(user)
        await db.flush()

        # Create audit log
        audit = AuditLog(
            user_id=user.id,
            user_email=user.email,
            action=AuditAction.USER_CREATE,
            resource_type="user",
            resource_id=str(user.id),
            description=f"User registered: {email}",
            ip_address=ip_address,
            user_agent=user_agent,
            organization_id=org.id,
        )
        db.add(audit)

        await db.commit()

        logger.info("User registered: %s (org: %s)", email, org_slug)
        return user

    @staticmethod
    async def authenticate_user(
        db: AsyncSession,
        email: str,
        password: str,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> User:
        """Authenticate user and return tokens."""
        result = await db.execute(
            select(User).where(
                User.email == email,
                User.is_active == True,
                User.deleted_at.is_(None),
            )
        )
        user = result.scalar_one_or_none()

        if not user or not verify_password(password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Create audit log
        audit = AuditLog(
            user_id=user.id,
            user_email=user.email,
            action=AuditAction.LOGIN,
            resource_type="user",
            resource_id=str(user.id),
            description=f"User logged in: {email}",
            ip_address=ip_address,
            user_agent=user_agent,
            organization_id=user.organization_id,
        )
        db.add(audit)
        await db.commit()

        logger.info("User login: %s (id: %s)", email, user.id)
        return user

    @staticmethod
    async def create_tokens(user: User) -> dict[str, str | int]:
        """Create access and refresh tokens."""
        from app.core.config import get_settings

        settings = get_settings()

        access_token = create_access_token(
            data={"sub": str(user.id), "email": user.email, "role": user.role}
        )
        refresh_token = create_refresh_token(data={"sub": str(user.id)})

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "expires_in": settings.access_token_expire_minutes * 60,
        }

    @staticmethod
    async def refresh_access_token(
        db: AsyncSession,
        refresh_token: str,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> dict[str, str | int]:
        """Refresh access token."""
        payload = decode_token(refresh_token)
        if not payload or payload.get("type") != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token",
                headers={"WWW-Authenticate": "Bearer"},
            )

        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token",
                headers={"WWW-Authenticate": "Bearer"},
            )

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

        # Create audit log
        audit = AuditLog(
            user_id=user.id,
            user_email=user.email,
            action=AuditAction.TOKEN_REFRESH,
            resource_type="user",
            resource_id=str(user.id),
            description="Token refreshed",
            ip_address=ip_address,
            user_agent=user_agent,
            organization_id=user.organization_id,
        )
        db.add(audit)
        await db.commit()

        logger.info("Token refreshed for user: %s", user.id)
        return await AuthService.create_tokens(user)

    @staticmethod
    async def change_password(
        db: AsyncSession,
        user: User,
        current_password: str,
        new_password: str,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> None:
        """Change user password."""
        if not verify_password(current_password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Current password is incorrect",
            )

        user.hashed_password = get_password_hash(new_password)

        # Create audit log
        audit = AuditLog(
            user_id=user.id,
            user_email=user.email,
            action=AuditAction.PASSWORD_CHANGE,
            resource_type="user",
            resource_id=str(user.id),
            description="Password changed",
            ip_address=ip_address,
            user_agent=user_agent,
            organization_id=user.organization_id,
        )
        db.add(audit)
        await db.commit()

        logger.info("Password changed for user: %s", user.id)

    @staticmethod
    async def logout(
        db: AsyncSession,
        user: User,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> None:
        """Log out user (create audit log)."""
        audit = AuditLog(
            user_id=user.id,
            user_email=user.email,
            action=AuditAction.LOGOUT,
            resource_type="user",
            resource_id=str(user.id),
            description=f"User logged out: {user.email}",
            ip_address=ip_address,
            user_agent=user_agent,
            organization_id=user.organization_id,
        )
        db.add(audit)
        await db.commit()

        logger.info("User logout: %s", user.id)
