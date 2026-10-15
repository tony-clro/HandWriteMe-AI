import os
import pytest
from fastapi.testclient import TestClient
from msflib.account.actions import verify_password
from sqlmodel import SQLModel, Session, create_engine, select

from app import models
from app.actions import account_action, user_action
from app.core.config import settings
from app.db.init_db import init_db
from app.main import sync_superuser_password_on_startup
from app.models import Account, AccountRole, AccountStatus, Tenant, User, Workspace
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


def test_first_startup_creates_default_records(tmp_path) -> None:
    """Non-destructive startup initialization on a fresh database creates default records."""
    db_file = tmp_path / "fresh_test.db"
    test_engine = create_engine(
        f"sqlite:///{db_file.as_posix()}",
        connect_args={"check_same_thread": False},
    )

    # 1. Non-destructively create schema
    SQLModel.metadata.create_all(test_engine)

    # 2. Run initialization with create_tables=False
    init_db(test_engine, create_tables=False)

    with Session(test_engine) as session:
        # Administrator account created with correct configured credentials and roles
        admin = account_action.get_by_email(session, email=settings.FIRST_SUPERUSER)
        assert admin is not None
        assert admin.email == settings.FIRST_SUPERUSER
        assert admin.role == AccountRole.admin
        assert admin.status == AccountStatus.active
        assert admin.hashed_password is not None
        assert verify_password(settings.FIRST_SUPERUSER_PASSWORD, admin.hashed_password)

        # Default tenant exists
        tenants = session.exec(select(Tenant)).all()
        assert len(tenants) >= 1

        # Default workspace exists owned by the administrator
        workspaces = session.exec(select(Workspace).where(Workspace.owner_id == admin.id)).all()
        assert len(workspaces) == 1
        workspace = workspaces[0]
        assert admin.current_workspace_id == workspace.id

        # Workspace membership exists
        membership = user_action.get_by_all(session, account_id=admin.id, workspace_id=workspace.id)
        assert membership is not None


def test_repeated_startup_does_not_create_duplicates(tmp_path) -> None:
    """Repeated startup runs are completely idempotent and do not duplicate accounts, tenants, workspaces, or memberships."""
    db_file = tmp_path / "idempotent_startup.db"
    test_engine = create_engine(
        f"sqlite:///{db_file.as_posix()}",
        connect_args={"check_same_thread": False},
    )

    SQLModel.metadata.create_all(test_engine)
    init_db(test_engine, create_tables=False)

    with Session(test_engine) as session:
        initial_accounts = len(session.exec(select(Account)).all())
        initial_tenants = len(session.exec(select(Tenant)).all())
        initial_workspaces = len(session.exec(select(Workspace)).all())
        initial_memberships = len(session.exec(select(User)).all())
        admin = account_action.get_by_email(session, email=settings.FIRST_SUPERUSER)
        assert admin is not None
        admin_id = admin.id

    # Simulate second and third container restarts or multiple worker processes
    init_db(test_engine, create_tables=False)
    init_db(test_engine, create_tables=False)

    with Session(test_engine) as session:
        assert len(session.exec(select(Account)).all()) == initial_accounts
        assert len(session.exec(select(Tenant)).all()) == initial_tenants
        assert len(session.exec(select(Workspace)).all()) == initial_workspaces
        assert len(session.exec(select(User)).all()) == initial_memberships

        refreshed_admin = account_action.get_by_email(session, email=settings.FIRST_SUPERUSER)
        assert refreshed_admin is not None
        assert refreshed_admin.id == admin_id


def test_existing_administrator_preserved_on_repeated_startup(tmp_path) -> None:
    """When an administrator account already exists, init_db does not alter or reset their password."""
    db_file = tmp_path / "preserve_existing.db"
    test_engine = create_engine(
        f"sqlite:///{db_file.as_posix()}",
        connect_args={"check_same_thread": False},
    )

    SQLModel.metadata.create_all(test_engine)
    init_db(test_engine, create_tables=False)

    custom_password = "CustomSuperuserPassword!123"
    with Session(test_engine) as session:
        admin = account_action.get_by_email(session, email=settings.FIRST_SUPERUSER)
        assert admin is not None
        # Update administrator password to something different from FIRST_SUPERUSER_PASSWORD
        account_action.update(session, model=admin, data=models.AccountUpdate(new_password=custom_password))
        session.commit()

        session.refresh(admin)
        assert verify_password(custom_password, admin.hashed_password)
        stored_hash = admin.hashed_password

    # Re-run init_db (e.g. app restart)
    init_db(test_engine, create_tables=False)

    with Session(test_engine) as session:
        admin_after = account_action.get_by_email(session, email=settings.FIRST_SUPERUSER)
        assert admin_after is not None
        # Password must not have been reverted to settings.FIRST_SUPERUSER_PASSWORD
        assert admin_after.hashed_password == stored_hash
        assert verify_password(custom_password, admin_after.hashed_password)


def test_create_tables_false_cannot_drop_or_recreate_existing_tables(tmp_path) -> None:
    """Verifies that create_tables=False never drops tables or existing user data."""
    db_file = tmp_path / "no_drop.db"
    test_engine = create_engine(
        f"sqlite:///{db_file.as_posix()}",
        connect_args={"check_same_thread": False},
    )

    SQLModel.metadata.create_all(test_engine)
    init_db(test_engine, create_tables=False)

    # Insert a normal account into the database
    with Session(test_engine) as session:
        normal_account = account_action.create(
            session,
            data=models.AccountCreate(
                username="user@example.com",
                email="user@example.com",
                phone="+15551234567",
                password="UserPassword123!",
                status=AccountStatus.active,
                role=AccountRole.user,
                profile=models.ProfileCreate(first_name="Normal", last_name="User"),
            ),
        )
        session.commit()
        user_id = normal_account.id

    # Run init_db with create_tables=False
    init_db(test_engine, create_tables=False)

    with Session(test_engine) as session:
        rechecked_user = account_action.get_by_email(session, email="user@example.com")
        assert rechecked_user is not None
        assert rechecked_user.id == user_id


def test_startup_initialization_sequence_end_to_end(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Simulates Render container cold boot: creates schema, bootstraps admin, then synchronizes password."""
    db_file = tmp_path / "cold_boot.db"
    test_engine = create_engine(
        f"sqlite:///{db_file.as_posix()}",
        connect_args={"check_same_thread": False},
    )

    render_new_password = "RenderSynchronizedPassword!789"
    monkeypatch.setenv("SYNC_SUPERUSER_PASSWORD", "true")
    monkeypatch.setenv("FIRST_SUPERUSER_PASSWORD", render_new_password)
    monkeypatch.setattr(settings, "FIRST_SUPERUSER_PASSWORD", render_new_password)

    # 1. DDL: Create schema
    SQLModel.metadata.create_all(test_engine)

    # 2. Seed default admin, tenant, workspace
    init_db(test_engine, create_tables=False)

    # 3. Synchronize password hook
    with Session(test_engine) as session:
        sync_result = sync_superuser_password_on_startup(session=session)
        assert sync_result is True

        admin = account_action.get_by_email(session, email=settings.FIRST_SUPERUSER)
        assert admin is not None
        # Admin is immediately authenticated with the synchronized password
        assert verify_password(render_new_password, admin.hashed_password)

