from datetime import timedelta
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.core import security
from app.core.config import settings
from app.models.user import User, UserRole
from app.repositories.user_repo import user_repository
from app.schemas.user import Token, UserCreate, UserOut
from app.services.auth_service import auth_service

router = APIRouter()


@router.post("/login", response_model=Token)
async def login_access_token(
    db: AsyncSession = Depends(deps.get_db),
    form_data: OAuth2PasswordRequestForm = Depends()
) -> Any:
    """
    OAuth2 compatible token login, get an access token for future requests.
    """
    user = await auth_service.authenticate(
        db, email=form_data.username, password=form_data.password
    )
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incorrect email or password"
        )
    elif not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user"
        )
        
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    return {
        "access_token": security.create_access_token(
            user.id, expires_delta=access_token_expires
        ),
        "token_type": "bearer",
    }


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def register_user(
    *,
    db: AsyncSession = Depends(deps.get_db),
    user_in: UserCreate,
    current_user: User = Depends(deps.RoleChecker([UserRole.ADMIN]))
) -> Any:
    """
    Create new user (restricted to Admin users).
    """
    user = await user_repository.get_by_email(db, email=user_in.email)
    if user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The user with this email already exists in the system.",
        )
    new_user = await user_repository.create(
        db,
        username=user_in.username,
        email=user_in.email,
        password=user_in.password,
        role=user_in.role
    )
    return new_user


@router.post("/setup-admin", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def setup_initial_admin(
    *,
    db: AsyncSession = Depends(deps.get_db),
    user_in: UserCreate
) -> Any:
    """
    Special endpoint to setup the first Admin user if no users exist.
    """
    # Check if any user exists
    from sqlalchemy import select, func
    from app.models.user import User
    result = await db.execute(select(func.count(User.id)))
    count = result.scalar()
    if count > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Admin setup is only allowed on an empty database."
        )
    
    new_user = await user_repository.create(
        db,
        username=user_in.username,
        email=user_in.email,
        password=user_in.password,
        role=UserRole.ADMIN
    )
    return new_user


@router.get("/me", response_model=UserOut)
async def read_user_me(
    current_user: User = Depends(deps.get_current_active_user)
) -> Any:
    """
    Get current active user.
    """
    return current_user
