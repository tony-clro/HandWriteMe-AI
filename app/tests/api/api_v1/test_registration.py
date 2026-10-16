from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.core.config import settings
from app.models import Account, AccountRole, AccountStatus, HandwritingProfile, Document


def test_user_registration_success(client: TestClient, session: Session) -> None:
    email = "test_new_user_success@example.com"
    password = "securePassword123!"
    full_name = "Jane Doe"

    # Ensure clean state
    existing = session.exec(select(Account).where(Account.email == email.lower())).first()
    if existing:
        if existing.profile:
            session.delete(existing.profile)
        session.delete(existing)
        session.commit()

    response = client.post(
        f"{settings.API_V1_STR}/register",
        json={
            "email": email,
            "password": password,
            "password_confirm": password,
            "full_name": full_name,
        },
    )
    assert response.status_code == 201, f"Expected 201, got {response.status_code}: {response.text}"
    data = response.json()
    assert data["email"] == email.lower()
    assert data["role"] == "user"
    assert data["status"] == "active"
    assert "hashed_password" not in data

    # Verify profile was created
    if "profile" in data and data["profile"]:
        assert data["profile"]["first_name"] == "Jane"
        assert data["profile"]["last_name"] == "Doe"

    # Verify database persistence
    db_account = session.exec(select(Account).where(Account.email == email.lower())).first()
    assert db_account is not None
    assert db_account.role == AccountRole.user
    assert db_account.status == AccountStatus.active
    assert db_account.current_workspace_id is not None, "Workspace context should be assigned"

    # Verify immediate login with newly registered credentials
    login_res = client.post(
        f"{settings.API_V1_STR}/login",
        data={"username": email, "password": password},
    )
    assert login_res.status_code == 200
    token_data = login_res.json()
    assert "access_token" in token_data
    assert token_data["token_type"] == "bearer"

    # Verify authenticated /me access
    headers = {"Authorization": f"Bearer {token_data['access_token']}"}
    me_res = client.get(f"{settings.API_V1_STR}/me", headers=headers)
    assert me_res.status_code == 200
    assert me_res.json()["email"] == email.lower()


def test_registration_open_alias_endpoint(client: TestClient, session: Session) -> None:
    email = "test_open_alias@example.com"
    password = "securePassword123!"

    existing = session.exec(select(Account).where(Account.email == email.lower())).first()
    if existing:
        if existing.profile:
            session.delete(existing.profile)
        session.delete(existing)
        session.commit()

    response = client.post(
        f"{settings.API_V1_STR}/open",
        json={
            "email": email,
            "password": password,
            "password_confirm": password,
            "full_name": "Alias User",
        },
    )
    assert response.status_code == 201
    assert response.json()["email"] == email.lower()


def test_registration_duplicate_email_rejected(client: TestClient) -> None:
    # Use existing superuser email
    response = client.post(
        f"{settings.API_V1_STR}/register",
        json={
            "email": settings.FIRST_SUPERUSER,
            "password": "password12345",
            "password_confirm": "password12345",
            "full_name": "Imposter Admin",
        },
    )
    assert response.status_code in {400, 422}
    detail = str(response.json().get("detail", "")).lower()
    assert "already exists" in detail or "conflict" in detail


def test_registration_password_mismatch_rejected(client: TestClient) -> None:
    response = client.post(
        f"{settings.API_V1_STR}/register",
        json={
            "email": "mismatch@example.com",
            "password": "correctPassword1!",
            "password_confirm": "differentPassword2!",
            "full_name": "Mismatch User",
        },
    )
    assert response.status_code == 422
    assert "match" in str(response.json()["detail"]).lower()


def test_registration_password_too_short_rejected(client: TestClient) -> None:
    response = client.post(
        f"{settings.API_V1_STR}/register",
        json={
            "email": "short@example.com",
            "password": "short",
            "password_confirm": "short",
        },
    )
    assert response.status_code == 422
    assert "at least 8" in str(response.json()["detail"]).lower()


def test_registration_invalid_email_rejected(client: TestClient) -> None:
    response = client.post(
        f"{settings.API_V1_STR}/register",
        json={
            "email": "not-an-email",
            "password": "validPassword123!",
            "password_confirm": "validPassword123!",
        },
    )
    assert response.status_code == 422


def test_registration_prevents_privilege_escalation(client: TestClient, session: Session) -> None:
    email = "attacker_privilege@example.com"
    password = "securePassword123!"

    existing = session.exec(select(Account).where(Account.email == email.lower())).first()
    if existing:
        if existing.profile:
            session.delete(existing.profile)
        session.delete(existing)
        session.commit()

    # Attempt to inject role="admin" and status="superuser"
    response = client.post(
        f"{settings.API_V1_STR}/register",
        json={
            "email": email,
            "password": password,
            "password_confirm": password,
            "role": "admin",
            "status": "active",
        },
    )
    assert response.status_code == 201
    created = response.json()
    assert created["role"] == "user", "Public registration must NEVER allow creating admin accounts"

    db_account = session.exec(select(Account).where(Account.email == email.lower())).first()
    assert db_account is not None
    assert db_account.role == AccountRole.user


def test_tenant_isolation_between_registered_users(
    client: TestClient,
    session: Session,
    superuser_account_token_headers: dict[str, str],
) -> None:
    """
    Verify that a newly registered user CANNOT access, view, or modify
    another user's handwriting profiles or documents.
    """
    user1_email = "tenant_user1@example.com"
    user2_email = "tenant_user2@example.com"
    passw = "securePassword123!"

    # Clean up any existing records
    for em in [user1_email, user2_email]:
        acc = session.exec(select(Account).where(Account.email == em.lower())).first()
        if acc:
            profiles = session.exec(select(HandwritingProfile).where(HandwritingProfile.account_id == acc.id)).all()
            for p in profiles:
                session.delete(p)
            docs = session.exec(select(Document).where(Document.account_id == acc.id)).all()
            for d in docs:
                session.delete(d)
            if acc.profile:
                session.delete(acc.profile)
            session.delete(acc)
            session.commit()

    # Register User 1
    r1 = client.post(
        f"{settings.API_V1_STR}/register",
        json={"email": user1_email, "password": passw, "password_confirm": passw, "full_name": "User One"},
    )
    assert r1.status_code == 201

    # Register User 2
    r2 = client.post(
        f"{settings.API_V1_STR}/register",
        json={"email": user2_email, "password": passw, "password_confirm": passw, "full_name": "User Two"},
    )
    assert r2.status_code == 201

    # Login User 1
    login1 = client.post(f"{settings.API_V1_STR}/login", data={"username": user1_email, "password": passw}).json()
    headers1 = {"Authorization": f"Bearer {login1['access_token']}"}

    # Login User 2
    login2 = client.post(f"{settings.API_V1_STR}/login", data={"username": user2_email, "password": passw}).json()
    headers2 = {"Authorization": f"Bearer {login2['access_token']}"}

    # User 1 creates a profile
    p1 = client.post(
        f"{settings.API_V1_STR}/handwriting-profiles/",
        headers=headers1,
        json={"name": "User 1 Secret Signature", "style_model": "lstm"},
    ).json()

    # User 1 creates a document
    d1 = client.post(
        f"{settings.API_V1_STR}/documents/text",
        headers=headers1,
        json={"title": "User 1 Confidential Memo", "text": "Confidential content for User 1 only."},
    ).json()

    # User 2 tries to GET User 1's profile -> MUST return 404
    p_cross = client.get(f"{settings.API_V1_STR}/handwriting-profiles/{p1['id']}", headers=headers2)
    assert p_cross.status_code == 404

    # User 2 lists profiles -> User 1's profile must NOT appear
    p_list = client.get(f"{settings.API_V1_STR}/handwriting-profiles/", headers=headers2).json()
    assert not any(p["id"] == p1["id"] for p in p_list)

    # User 2 tries to GET User 1's document -> MUST return 404
    d_cross = client.get(f"{settings.API_V1_STR}/documents/{d1['id']}", headers=headers2)
    assert d_cross.status_code == 404

    # User 2 lists documents -> User 1's document must NOT appear
    d_list = client.get(f"{settings.API_V1_STR}/documents/", headers=headers2).json()
    assert not any(d["id"] == d1["id"] for d in d_list)

    # User 2 tries to export User 1's document -> MUST return 404
    exp_cross = client.get(f"{settings.API_V1_STR}/documents/{d1['id']}/export", headers=headers2)
    assert exp_cross.status_code == 404
