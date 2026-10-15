import os
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.actions import account_action
from app.core.config import settings
from app.main import sync_superuser_password_on_startup
from app.models import Account, AccountRole, AccountStatus
from app.reset_superuser import reset_superuser_password


def test_startup_disabled_flag_does_not_reset_password(
    client: TestClient, session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When SYNC_SUPERUSER_PASSWORD is unset, false, or empty, startup hook does nothing."""
    account_before = account_action.get_by_email(session, email=settings.FIRST_SUPERUSER)
    assert account_before is not None
    original_hash = account_before.hashed_password

    # Test with unset flag
    monkeypatch.delenv("SYNC_SUPERUSER_PASSWORD", raising=False)
    result_unset = sync_superuser_password_on_startup(session=session)
    assert result_unset is None

    # Test with explicit false
    monkeypatch.setenv("SYNC_SUPERUSER_PASSWORD", "false")
    result_false = sync_superuser_password_on_startup(session=session)
    assert result_false is None

    # Test with empty string
    monkeypatch.setenv("SYNC_SUPERUSER_PASSWORD", "   ")
    result_empty = sync_superuser_password_on_startup(session=session)
    assert result_empty is None

    session.refresh(account_before)
    assert account_before.hashed_password == original_hash


def test_startup_enabled_flag_updates_password_and_authenticates(
    client: TestClient, session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Enabling SYNC_SUPERUSER_PASSWORD updates the administrator password, authenticates new, rejects old."""
    original_password = settings.FIRST_SUPERUSER_PASSWORD
    new_password = "SyncSecurePassword!987"

    try:
        # Enable the sync flag and configure new password
        monkeypatch.setenv("SYNC_SUPERUSER_PASSWORD", "true")
        monkeypatch.setenv("FIRST_SUPERUSER_PASSWORD", new_password)
        monkeypatch.setattr(settings, "FIRST_SUPERUSER_PASSWORD", new_password)

        result = sync_superuser_password_on_startup(session=session)
        assert result is True

        # New password authenticates
        login_res = client.post(
            f"{settings.API_V1_STR}/login",
            data={"username": settings.FIRST_SUPERUSER, "password": new_password},
        )
        assert login_res.status_code == 200
        assert "access_token" in login_res.json()

        # Old password is rejected
        bad_res = client.post(
            f"{settings.API_V1_STR}/login",
            data={"username": settings.FIRST_SUPERUSER, "password": original_password},
        )
        assert bad_res.status_code == 400
        assert "Incorrect email or password" in bad_res.json()["detail"]

    finally:
        # Restore original password
        reset_superuser_password(
            email=settings.FIRST_SUPERUSER,
            new_password=original_password,
            session=session,
        )


def test_startup_preserves_account_identity_role_tenant_and_data(
    client: TestClient, session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Password synchronization preserves account identity, role, tenant, workspace and creates no duplicates."""
    account_before = account_action.get_by_email(session, email=settings.FIRST_SUPERUSER)
    assert account_before is not None

    account_id_before = account_before.id
    email_before = account_before.email
    role_before = account_before.role
    status_before = account_before.status
    workspace_id_before = account_before.current_workspace_id

    total_accounts_before = len(session.exec(select(Account)).all())

    temp_password = "PreserveAttributesPassword!456"
    try:
        monkeypatch.setenv("SYNC_SUPERUSER_PASSWORD", "true")
        monkeypatch.setenv("FIRST_SUPERUSER_PASSWORD", temp_password)
        monkeypatch.setattr(settings, "FIRST_SUPERUSER_PASSWORD", temp_password)

        result = sync_superuser_password_on_startup(session=session)
        assert result is True

        session.refresh(account_before)

        # Verify identity and attributes are identical
        assert account_before.id == account_id_before
        assert account_before.email == email_before
        assert account_before.role == role_before
        assert account_before.status == status_before
        assert account_before.current_workspace_id == workspace_id_before

        # Verify no duplicate accounts were created
        total_accounts_after = len(session.exec(select(Account)).all())
        assert total_accounts_after == total_accounts_before

    finally:
        reset_superuser_password(
            email=settings.FIRST_SUPERUSER,
            new_password=settings.FIRST_SUPERUSER_PASSWORD,
            session=session,
        )


def test_repeated_startup_idempotency_prevents_rehash(
    client: TestClient, session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Repeated startup executions are idempotent: once synchronized, no subsequent password re-hashing occurs."""
    sync_password = "IdempotentSyncPassword!321"

    try:
        monkeypatch.setenv("SYNC_SUPERUSER_PASSWORD", "true")
        monkeypatch.setenv("FIRST_SUPERUSER_PASSWORD", sync_password)
        monkeypatch.setattr(settings, "FIRST_SUPERUSER_PASSWORD", sync_password)

        # First synchronization: updates the password
        first_run = sync_superuser_password_on_startup(session=session)
        assert first_run is True

        account = account_action.get_by_email(session, email=settings.FIRST_SUPERUSER)
        assert account is not None
        hash_after_first = account.hashed_password

        # Second synchronization (simulating worker 2 or service restart):
        # Because the password is already synchronized, verify_password matches and update is skipped.
        second_run = sync_superuser_password_on_startup(session=session)
        assert second_run is True

        session.refresh(account)
        hash_after_second = account.hashed_password

        # Bcrypt generates a different salt every time it hashes.
        # If an update had occurred, the hash would differ.
        # Equal hashes prove zero redundant database write occurred.
        assert hash_after_second == hash_after_first

    finally:
        reset_superuser_password(
            email=settings.FIRST_SUPERUSER,
            new_password=settings.FIRST_SUPERUSER_PASSWORD,
            session=session,
        )


def test_startup_fails_safely_when_account_missing_or_password_invalid(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Startup hook handles missing account or invalid password safely without crashing or exposing secrets."""
    monkeypatch.setenv("SYNC_SUPERUSER_PASSWORD", "true")

    # Nonexistent account
    monkeypatch.setenv("FIRST_SUPERUSER", "ghost@example.com")
    monkeypatch.setattr(settings, "FIRST_SUPERUSER", "ghost@example.com")
    monkeypatch.setenv("FIRST_SUPERUSER_PASSWORD", "ValidPassword123!")
    monkeypatch.setattr(settings, "FIRST_SUPERUSER_PASSWORD", "ValidPassword123!")

    result_missing = sync_superuser_password_on_startup(session=session)
    assert result_missing is False

    # Invalid short password
    monkeypatch.setenv("FIRST_SUPERUSER", "admin@example.com")
    monkeypatch.setattr(settings, "FIRST_SUPERUSER", "admin@example.com")
    monkeypatch.setenv("FIRST_SUPERUSER_PASSWORD", "short")
    monkeypatch.setattr(settings, "FIRST_SUPERUSER_PASSWORD", "short")

    result_invalid = sync_superuser_password_on_startup(session=session)
    assert result_invalid is False
