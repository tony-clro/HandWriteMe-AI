from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.config import settings


def test_use_access_token(
    client: TestClient, superuser_account_token_headers: dict[str, str]
) -> None:
    r = client.get(
        f"{settings.API_V1_STR}/me",
        headers=superuser_account_token_headers,
    )
    result = r.json()
    assert r.status_code == 200
    assert result["email"] == settings.FIRST_SUPERUSER.lower()


def test_clear_access_token(
    client: TestClient, superuser_account_token_headers: dict[str, str]
) -> None:
    r = client.get(
        f"{settings.API_V1_STR}/me",
        headers=superuser_account_token_headers,
    )
    assert r.status_code == 200

    r1 = client.delete(
        f"{settings.API_V1_STR}/logout",
        headers=superuser_account_token_headers,
    )
    assert r1.status_code == 200

    r2 = client.get(
        f"{settings.API_V1_STR}/me",
        headers=superuser_account_token_headers,
    )
    assert r2.status_code in {401, 403}

    r3 = client.post(
        f"{settings.API_V1_STR}/login",
        data={
            "username": settings.FIRST_SUPERUSER.upper(),
            "password": settings.FIRST_SUPERUSER_PASSWORD,
        },
    )
    assert r3.status_code == 200
    token = r3.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    r4 = client.get(
        f"{settings.API_V1_STR}/me",
        headers=headers,
    )
    assert r4.status_code == 200


def test_handwriting_profiles_unauthenticated_returns_401(client: TestClient) -> None:
    response = client.get(f"{settings.API_V1_STR}/handwriting-profiles/")
    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"


def test_documents_unauthenticated_returns_401(client: TestClient) -> None:
    response = client.get(f"{settings.API_V1_STR}/documents/")
    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"


def test_login_invalid_password_returns_400(client: TestClient) -> None:
    response = client.post(
        f"{settings.API_V1_STR}/login",
        data={
            "username": settings.FIRST_SUPERUSER,
            "password": "wrong-password-12345",
        },
    )
    assert response.status_code == 400
    assert "Incorrect email or password" in response.json()["detail"]


def test_login_and_authenticated_endpoints(client: TestClient) -> None:
    # 1. Login with valid seed superuser credentials
    login_res = client.post(
        f"{settings.API_V1_STR}/login",
        data={
            "username": settings.FIRST_SUPERUSER,
            "password": settings.FIRST_SUPERUSER_PASSWORD,
        },
    )
    assert login_res.status_code == 200
    payload = login_res.json()
    assert "access_token" in payload
    assert payload.get("token_type") == "bearer"
    token = payload["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Access handwriting profiles endpoint with valid bearer token
    profiles_res = client.get(f"{settings.API_V1_STR}/handwriting-profiles/", headers=headers)
    assert profiles_res.status_code == 200
    assert isinstance(profiles_res.json(), list)

    # 3. Access documents endpoint with valid bearer token
    docs_res = client.get(f"{settings.API_V1_STR}/documents/", headers=headers)
    assert docs_res.status_code == 200
    assert isinstance(docs_res.json(), list)


def test_sample_file_query_token_auth(
    client: TestClient, superuser_account_token_headers: dict[str, str]
) -> None:
    # Unauthenticated request without token or header returns 401
    unauth_res = client.get(f"{settings.API_V1_STR}/handwriting-profiles/1/samples/1/file")
    assert unauth_res.status_code == 401
    assert unauth_res.json()["detail"] == "Not authenticated"

    # Request with invalid token returns 401
    bad_token_res = client.get(
        f"{settings.API_V1_STR}/handwriting-profiles/1/samples/1/file?token=invalid.jwt.token"
    )
    assert bad_token_res.status_code == 401

    # Extract valid token from header
    token = superuser_account_token_headers["Authorization"].split(" ")[1]
    # Request with valid query parameter token passes auth (returns 404 because sample doesn't exist, NOT 401)
    valid_token_res = client.get(
        f"{settings.API_V1_STR}/handwriting-profiles/1/samples/1/file?token={token}"
    )
    assert valid_token_res.status_code == 404
    assert valid_token_res.json()["detail"] == "Sample not found."


def test_reset_superuser_password_authenticates_and_rejects_incorrect(
    client: TestClient, session: Session
) -> None:
    from app.reset_superuser import reset_superuser_password

    original_password = settings.FIRST_SUPERUSER_PASSWORD
    new_password = "TemporaryResetSecretPassword!456"

    try:
        # 1. Reset password for superuser
        success = reset_superuser_password(
            email=settings.FIRST_SUPERUSER,
            new_password=new_password,
            session=session,
        )
        assert success is True

        # 2. Verify login with the new password succeeds
        valid_res = client.post(
            f"{settings.API_V1_STR}/login",
            data={
                "username": settings.FIRST_SUPERUSER,
                "password": new_password,
            },
        )
        assert valid_res.status_code == 200
        payload = valid_res.json()
        assert "access_token" in payload
        assert payload.get("token_type") == "bearer"

        # 3. Verify login with old/wrong password fails
        bad_res = client.post(
            f"{settings.API_V1_STR}/login",
            data={
                "username": settings.FIRST_SUPERUSER,
                "password": "definitely-wrong-password",
            },
        )
        assert bad_res.status_code == 400
        assert "Incorrect email or password" in bad_res.json()["detail"]

    finally:
        # Restore original password so test suite state remains clean
        reset_superuser_password(
            email=settings.FIRST_SUPERUSER,
            new_password=original_password,
            session=session,
        )


