"""Authentication API routes."""

from typing import Any

from fastapi import APIRouter, HTTPException, Request, Response, status

from app.api.schemas import (
    PasswordChange,
    TokenRefresh,
    TokenResponse,
    UserLogin,
    UserRegister,
    UserResponse,
)
from app.core.deps import CurrentUser, DBSession, OptionalUser, get_optional_user
from app.core.logging_config import get_logger
from app.services.auth_service import AuthService

logger = get_logger(__name__)
router = APIRouter()


def get_client_info(request: Request) -> tuple[str | None, str | None]:
    """Get client IP and user agent from request."""
    forwarded_for = request.headers.get("x-forwarded-for")
    ip_address = forwarded_for.split(",")[0].strip() if forwarded_for else request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    return ip_address, user_agent


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register new user",
    description="""
    Create a new user account with an associated organization.
    
    This endpoint will:
    - Create a new organization
    - Create a user account linked to that organization
    - Set the user as organization admin
    - Return the created user data
    
    **Note:** Email must be unique across the system.
    """,
    responses={
        status.HTTP_201_CREATED: {"description": "User created successfully"},
        status.HTTP_400_BAD_REQUEST: {"description": "Email already registered or invalid data"},
        status.HTTP_422_UNPROCESSABLE_ENTITY: {"description": "Validation error"},
    },
)
async def register(
    request: Request,
    data: UserRegister,
    db: DBSession,
) -> Any:
    """Register a new user with organization."""
    ip_address, user_agent = get_client_info(request)
    
    user = await AuthService.register_user(
        db=db,
        email=data.email,
        password=data.password,
        full_name=data.full_name,
        organization_name=data.organization_name,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    return user


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="User login",
    description="""
    Authenticate a user and receive JWT access and refresh tokens.
    
    The endpoint will:
    - Validate email and password
    - Update last login timestamp
    - Create access token (15 min expiration)
    - Create refresh token (7 days expiration)
    - Set HTTP-only cookie for web sessions
    
    **Test Credentials:**
    - Email: `admin@example.com`
    - Password: `admin123`
    """,
    responses={
        status.HTTP_200_OK: {"description": "Login successful"},
        status.HTTP_401_UNAUTHORIZED: {"description": "Invalid credentials"},
        status.HTTP_422_UNPROCESSABLE_ENTITY: {"description": "Validation error"},
    },
)
async def login(
    request: Request,
    data: UserLogin,
    db: DBSession,
    response: Response,
) -> Any:
    """Authenticate user and return tokens."""
    ip_address, user_agent = get_client_info(request)
    
    user = await AuthService.authenticate_user(
        db=db,
        email=data.email,
        password=data.password,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    
    tokens = await AuthService.create_tokens(user)
    
    # Set cookie for web sessions
    response.set_cookie(
        key="access_token",
        value=tokens["access_token"],
        httponly=True,
        secure=False,  # Set to True in production with HTTPS
        samesite="lax",
        max_age=tokens["expires_in"],
    )
    
    return tokens


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    request: Request,
    data: TokenRefresh,
    db: DBSession,
    response: Response,
) -> Any:
    """Refresh access token."""
    ip_address, user_agent = get_client_info(request)
    
    tokens = await AuthService.refresh_access_token(
        db=db,
        refresh_token=data.refresh_token,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    
    # Update cookie
    response.set_cookie(
        key="access_token",
        value=tokens["access_token"],
        httponly=True,
        secure=False,
        samesite="lax",
        max_age=tokens["expires_in"],
    )
    
    return tokens


@router.post("/logout")
async def logout(
    request: Request,
    db: DBSession,
    user: CurrentUser,
    response: Response,
) -> dict[str, str]:
    """Log out user."""
    ip_address, user_agent = get_client_info(request)
    
    await AuthService.logout(
        db=db,
        user=user,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    
    # Clear cookie
    response.delete_cookie(key="access_token")
    
    return {"message": "Successfully logged out"}


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(user: CurrentUser) -> Any:
    """Get current user information."""
    return user


@router.post("/change-password")
async def change_password(
    request: Request,
    data: PasswordChange,
    db: DBSession,
    user: CurrentUser,
) -> dict[str, str]:
    """Change user password."""
    ip_address, user_agent = get_client_info(request)
    
    await AuthService.change_password(
        db=db,
        user=user,
        current_password=data.current_password,
        new_password=data.new_password,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    
    return {"message": "Password changed successfully"}
