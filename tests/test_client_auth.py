import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.main import app
from app.core.database import get_db
from app.models.client import Client
from app.services.client_auth_service import ClientAuthService

client = TestClient(app)


def test_create_client():
    """Test client creation"""
    client_data = {
        "client_id": "test-odoo-instance",
        "name": "Test Odoo Instance",
        "description": "Test client for Odoo integration",
        "permissions": ["projects:read", "elevations:read"],
        "rate_limit_per_hour": 1000
    }
    
    response = client.post("/api/v1/client-auth/register", json=client_data)
    
    assert response.status_code == 200
    data = response.json()
    assert data["client_id"] == "test-odoo-instance"
    assert data["name"] == "Test Odoo Instance"
    assert "client_secret" in data
    assert len(data["client_secret"]) > 20  # Should be a secure random string


def test_authenticate_client():
    """Test client authentication"""
    # First create a client
    client_data = {
        "client_id": "test-auth-client",
        "name": "Test Auth Client",
        "permissions": ["projects:read"]
    }
    
    create_response = client.post("/api/v1/client-auth/register", json=client_data)
    assert create_response.status_code == 200
    client_secret = create_response.json()["client_secret"]
    
    # Now authenticate
    auth_data = {
        "client_id": "test-auth-client",
        "client_secret": client_secret
    }
    
    auth_response = client.post("/api/v1/client-auth/login", json=auth_data)
    
    assert auth_response.status_code == 200
    data = auth_response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["expires_in"] == 24 * 60 * 60  # 24 hours
    assert "client_info" in data


def test_authenticate_invalid_client():
    """Test authentication with invalid credentials"""
    auth_data = {
        "client_id": "nonexistent-client",
        "client_secret": "invalid-secret"
    }
    
    response = client.post("/api/v1/client-auth/login", json=auth_data)
    
    assert response.status_code == 401
    data = response.json()
    assert data["detail"]["code"] == "INVALID_CREDENTIALS"


def test_duplicate_client_id():
    """Test creating client with duplicate ID"""
    client_data = {
        "client_id": "duplicate-test",
        "name": "First Client"
    }
    
    # Create first client
    response1 = client.post("/api/v1/client-auth/register", json=client_data)
    assert response1.status_code == 200
    
    # Try to create second client with same ID
    response2 = client.post("/api/v1/client-auth/register", json=client_data)
    assert response2.status_code == 400
    data = response2.json()
    assert data["detail"]["code"] == "CLIENT_ID_EXISTS"


def test_get_current_client_info():
    """Test getting current client info with valid token"""
    # Create and authenticate client
    client_data = {
        "client_id": "info-test-client",
        "name": "Info Test Client",
        "permissions": ["admin:read"]
    }
    
    create_response = client.post("/api/v1/client-auth/register", json=client_data)
    client_secret = create_response.json()["client_secret"]
    
    auth_response = client.post("/api/v1/client-auth/login", json={
        "client_id": "info-test-client",
        "client_secret": client_secret
    })
    access_token = auth_response.json()["access_token"]
    
    # Get client info
    headers = {"Authorization": f"Bearer {access_token}"}
    response = client.get("/api/v1/client-auth/me", headers=headers)
    
    assert response.status_code == 200
    data = response.json()
    assert data["client_id"] == "info-test-client"
    assert data["name"] == "Info Test Client"


def test_get_current_client_info_invalid_token():
    """Test getting client info with invalid token"""
    headers = {"Authorization": "Bearer invalid-token"}
    response = client.get("/api/v1/client-auth/me", headers=headers)
    
    assert response.status_code == 401


def test_list_clients():
    """Test listing clients (admin endpoint)"""
    # Create and authenticate admin client
    client_data = {
        "client_id": "admin-test-client",
        "name": "Admin Test Client",
        "permissions": ["admin:read"]
    }
    
    create_response = client.post("/api/v1/client-auth/register", json=client_data)
    client_secret = create_response.json()["client_secret"]
    
    auth_response = client.post("/api/v1/client-auth/login", json={
        "client_id": "admin-test-client",
        "client_secret": client_secret
    })
    access_token = auth_response.json()["access_token"]
    
    # List clients
    headers = {"Authorization": f"Bearer {access_token}"}
    response = client.get("/api/v1/client-auth/clients", headers=headers)
    
    assert response.status_code == 200
    data = response.json()
    assert "clients" in data
    assert "count" in data
    assert data["count"] >= 1  # At least the admin client we just created


def test_list_clients_without_admin_permission():
    """Test listing clients without admin permission"""
    # Create and authenticate non-admin client
    client_data = {
        "client_id": "non-admin-client",
        "name": "Non Admin Client",
        "permissions": ["projects:read"]  # No admin:read permission
    }
    
    create_response = client.post("/api/v1/client-auth/register", json=client_data)
    client_secret = create_response.json()["client_secret"]
    
    auth_response = client.post("/api/v1/client-auth/login", json={
        "client_id": "non-admin-client",
        "client_secret": client_secret
    })
    access_token = auth_response.json()["access_token"]
    
    # Try to list clients
    headers = {"Authorization": f"Bearer {access_token}"}
    response = client.get("/api/v1/client-auth/clients", headers=headers)
    
    assert response.status_code == 403
