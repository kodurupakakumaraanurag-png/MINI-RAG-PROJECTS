from unittest.mock import patch, AsyncMock, MagicMock
from uuid import uuid4
from datetime import datetime, timezone
import pytest
from fastapi import status
from app.models.user import User, UserRole
from app.core import security

@pytest.mark.asyncio
async def test_health_check(client) -> None:
    response = await client.get("/health")
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"status": "healthy", "service": "Tender War Room AI"}


@pytest.mark.asyncio
@patch("app.api.v1.endpoints.auth.user_repository")
async def test_setup_admin_success(mock_repo, client, mock_db_session) -> None:
    # Mock database query: count(User.id) returns 0
    mock_result = MagicMock()
    mock_result.scalar.return_value = 0
    mock_db_session.execute.return_value = mock_result
    
    # Mock user creation
    mock_user = User(
        id=uuid4(),
        username="admin",
        email="admin@example.com",
        role=UserRole.ADMIN,
        is_active=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc)
    )
    mock_repo.create = AsyncMock(return_value=mock_user)
    
    response = await client.post(
        "/api/v1/auth/setup-admin",
        json={
            "username": "admin",
            "email": "admin@example.com",
            "password": "strongpassword",
            "role": "Admin"
        }
    )
    
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert data["email"] == "admin@example.com"
    assert data["role"] == "Admin"


@pytest.mark.asyncio
@patch("app.api.v1.endpoints.auth.user_repository")
async def test_setup_admin_already_exists(mock_repo, client, mock_db_session) -> None:
    # Mock database query: count(User.id) returns 1 (already exists)
    mock_result = MagicMock()
    mock_result.scalar.return_value = 1
    mock_db_session.execute.return_value = mock_result
    
    response = await client.post(
        "/api/v1/auth/setup-admin",
        json={
            "username": "admin",
            "email": "admin@example.com",
            "password": "strongpassword",
            "role": "Admin"
        }
    )
    
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "empty database" in response.json()["detail"]


@pytest.mark.asyncio
@patch("app.api.v1.endpoints.auth.auth_service")
async def test_login_success(mock_auth, client) -> None:
    user_id = uuid4()
    mock_user = User(
        id=user_id,
        username="testuser",
        email="test@example.com",
        role=UserRole.CONTRACTOR,
        is_active=True
    )
    mock_auth.authenticate = AsyncMock(return_value=mock_user)
    
    response = await client.post(
        "/api/v1/auth/login",
        data={
            "username": "test@example.com",
            "password": "password123"
        }
    )
    
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
@patch("app.api.v1.endpoints.auth.auth_service")
async def test_login_invalid_credentials(mock_auth, client) -> None:
    mock_auth.authenticate = AsyncMock(return_value=None)
    
    response = await client.post(
        "/api/v1/auth/login",
        data={
            "username": "test@example.com",
            "password": "wrongpassword"
        }
    )
    
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "Incorrect email" in response.json()["detail"]


@pytest.mark.asyncio
@patch("app.api.deps.user_repository")
async def test_get_me_authenticated(mock_repo, client) -> None:
    user_uuid = uuid4()
    mock_user = User(
        id=user_uuid,
        username="john",
        email="john@example.com",
        role=UserRole.CONTRACTOR,
        is_active=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc)
    )
    # Mock deps.get_current_user loading by UUID
    mock_repo.get = AsyncMock(return_value=mock_user)
    
    # Generate token
    token = security.create_access_token(subject=user_uuid)
    
    response = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["email"] == "john@example.com"
    assert data["username"] == "john"
