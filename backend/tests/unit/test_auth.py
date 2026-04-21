"""Authentication tests."""

import pytest
from fastapi import HTTPException

from app.core.security import create_access_token, decode_token, get_password_hash, verify_password
from app.services.auth_service import AuthService


class TestPasswordSecurity:
    """Test password hashing and verification."""

    def test_password_hashing(self):
        """Test password hashing."""
        password = "testpassword123"
        hashed = get_password_hash(password)
        assert hashed != password
        assert verify_password(password, hashed)

    def test_password_verification_failure(self):
        """Test password verification with wrong password."""
        password = "testpassword123"
        wrong_password = "wrongpassword"
        hashed = get_password_hash(password)
        assert not verify_password(wrong_password, hashed)


class TestTokenSecurity:
    """Test JWT token creation and validation."""

    def test_create_and_decode_access_token(self):
        """Test access token creation and decoding."""
        data = {"sub": "user-123", "email": "test@example.com"}
        token = create_access_token(data)
        assert token is not None

        decoded = decode_token(token)
        assert decoded is not None
        assert decoded["sub"] == "user-123"
        assert decoded["email"] == "test@example.com"
        assert decoded["type"] == "access"

    def test_create_and_decode_refresh_token(self):
        """Test refresh token creation and decoding."""
        data = {"sub": "user-123"}
        token = create_refresh_token(data)
        assert token is not None

        decoded = decode_token(token)
        assert decoded is not None
        assert decoded["sub"] == "user-123"
        assert decoded["type"] == "refresh"

    def test_decode_invalid_token(self):
        """Test decoding invalid token."""
        decoded = decode_token("invalid-token")
        assert decoded is None


class TestAuthService:
    """Test authentication service."""

    @pytest.mark.asyncio
    async def test_register_user_success(self, db):
        """Test successful user registration."""
        user = await AuthService.register_user(
            db=db,
            email="new@example.com",
            password="password123",
            full_name="New User",
            organization_name="New Org",
        )

        assert user.email == "new@example.com"
        assert user.full_name == "New User"
        assert user.role.value == "admin"
        assert user.organization is not None

    @pytest.mark.asyncio
    async def test_register_user_duplicate_email(self, db, test_user):
        """Test registration with duplicate email."""
        with pytest.raises(HTTPException) as exc_info:
            await AuthService.register_user(
                db=db,
                email=test_user.email,  # Duplicate email
                password="password123",
                full_name="Another User",
                organization_name="Another Org",
            )
        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_authenticate_user_success(self, db, test_user):
        """Test successful authentication."""
        user = await AuthService.authenticate_user(
            db=db,
            email=test_user.email,
            password="test123",
        )
        assert user.id == test_user.id

    @pytest.mark.asyncio
    async def test_authenticate_user_wrong_password(self, db, test_user):
        """Test authentication with wrong password."""
        with pytest.raises(HTTPException) as exc_info:
            await AuthService.authenticate_user(
                db=db,
                email=test_user.email,
                password="wrongpassword",
            )
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_create_tokens(self, test_user):
        """Test token creation."""
        tokens = await AuthService.create_tokens(test_user)
        
        assert "access_token" in tokens
        assert "refresh_token" in tokens
        assert tokens["token_type"] == "bearer"
        assert "expires_in" in tokens

    @pytest.mark.asyncio
    async def test_change_password_success(self, db, test_user):
        """Test successful password change."""
        await AuthService.change_password(
            db=db,
            user=test_user,
            current_password="test123",
            new_password="newpassword123",
        )
        
        # Verify new password works
        assert verify_password("newpassword123", test_user.hashed_password)

    @pytest.mark.asyncio
    async def test_change_password_wrong_current(self, db, test_user):
        """Test password change with wrong current password."""
        with pytest.raises(HTTPException) as exc_info:
            await AuthService.change_password(
                db=db,
                user=test_user,
                current_password="wrongpassword",
                new_password="newpassword123",
            )
        assert exc_info.value.status_code == 400
