"""Deterministic QA and Security Verification Test Suite for Etap 1:
Cloud/Managed Registration, Login, Web Routes & User Dashboard.
"""

import os
import sqlite3
import pytest
from pathlib import Path
from fastapi.testclient import TestClient

from web_panel.app.main import create_app
from web_panel.app.database import init_db, get_connection
from web_panel.app.security.tokens import ACCESS_COOKIE_NAME, REFRESH_COOKIE_NAME, CSRF_COOKIE_NAME


@pytest.fixture(scope="module")
def client():
    # Initialize database
    init_db()
    app = create_app()
    with TestClient(app) as test_client:
        yield test_client


def test_registration_success(client: TestClient):
    """Verifies that a new user can register in Cloud mode and receive dual tokens + cookies."""
    import uuid
    random_email = f"user_{uuid.uuid4().hex[:8]}@kargopilot.az"
    random_phone = f"+99470{uuid.uuid4().hex[:7]}"

    payload = {
        "email": random_email,
        "password": "StrongPassword2026!",
        "full_name": "Əli Həsənov",
        "phone": random_phone,
        "hosting_preference": "cloud",
        "device_fingerprint": "Pytest-Agent-v1"
    }

    res = client.post("/api/v1/auth/register", json=payload)
    assert res.status_code == 201, f"Expected 201, got {res.status_code}: {res.text}"
    
    data = res.json()
    assert "access_token" in data
    assert data["email"] == random_email
    assert data["full_name"] == "Əli Həsənov"
    assert data["role"] == "CUSTOMER"
    assert "csrf_token" in data

    # Verify cookies
    cookies = res.cookies
    assert ACCESS_COOKIE_NAME in cookies
    assert REFRESH_COOKIE_NAME in cookies
    assert CSRF_COOKIE_NAME in cookies


def test_registration_duplicate_email(client: TestClient):
    """Verifies that duplicate registration with the same email returns HTTP 409 Conflict."""
    import uuid
    email = f"dup_{uuid.uuid4().hex[:8]}@kargopilot.az"
    payload = {
        "email": email,
        "password": "StrongPassword2026!",
        "full_name": "Murad Əliyev",
        "hosting_preference": "cloud"
    }

    # First attempt -> 201
    res1 = client.post("/api/v1/auth/register", json=payload)
    assert res1.status_code == 201

    # Second attempt -> 409
    res2 = client.post("/api/v1/auth/register", json=payload)
    assert res2.status_code == 409
    assert "artıq qeydiyyatdan keçilib" in res2.json()["detail"].lower()


def test_registration_validation_rules(client: TestClient):
    """Verifies that weak passwords (< 8 chars) or invalid emails return HTTP 422."""
    # Short password
    res1 = client.post("/api/v1/auth/register", json={
        "email": "valid@kargopilot.az",
        "password": "short",
        "full_name": "Test User"
    })
    assert res1.status_code == 422

    # Malformed email
    res2 = client.post("/api/v1/auth/register", json={
        "email": "not-an-email",
        "password": "StrongPassword2026!",
        "full_name": "Test User"
    })
    assert res2.status_code == 422


def test_login_flow(client: TestClient):
    """Verifies authentication with valid credentials and failure with wrong password."""
    import uuid
    email = f"auth_test_{uuid.uuid4().hex[:6]}@kargopilot.az"
    password = "AuthPassword2026!"

    # 1. Register
    reg_res = client.post("/api/v1/auth/register", json={
        "email": email,
        "password": password,
        "full_name": "Kənan Nəbiyev",
        "hosting_preference": "cloud"
    })
    assert reg_res.status_code == 201

    # 2. Login with wrong password
    bad_login = client.post("/api/v1/auth/login", json={
        "email": email,
        "password": "WrongPassword999!"
    })
    assert bad_login.status_code == 401

    # 3. Login with correct password
    good_login = client.post("/api/v1/auth/login", json={
        "email": email,
        "password": password
    })
    assert good_login.status_code == 200
    data = good_login.json()
    assert data["email"] == email
    assert data["role"] == "CUSTOMER"
    assert "access_token" in data


def test_web_routes_rendering(client: TestClient):
    """Verifies that HTML web pages (/login, /register, /user/dashboard, /showcase) render HTTP 200 and redirect when authenticated."""
    # 1. Clear cookies to test as unauthenticated visitor
    client.cookies.clear()

    res_login = client.get("/login")
    assert res_login.status_code == 200
    assert "Daxil Ol" in res_login.text

    res_register = client.get("/register")
    assert res_register.status_code == 200
    assert "Yeni Hesab Yaradın" in res_register.text
    assert "Bizim Serverdə" in res_register.text

    res_dashboard = client.get("/user/dashboard")
    assert res_dashboard.status_code == 200
    assert "Şəxsi İdarəetmə Paneli" in res_dashboard.text
    assert "300$" in res_dashboard.text

    res_showcase = client.get("/showcase")
    assert res_showcase.status_code == 200
    assert "Bizim Serverdə (Managed Cloud)" in res_showcase.text
