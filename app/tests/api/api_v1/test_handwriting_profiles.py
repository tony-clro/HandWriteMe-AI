from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.config import settings
from app.models import HandwritingProfile


def test_create_handwriting_profile(
    client: TestClient,
    superuser_account_token_headers: dict[str, str],
) -> None:
    response = client.post(
        f"{settings.API_V1_STR}/handwriting-profiles/",
        headers=superuser_account_token_headers,
        json={
            "name": "My Personal Style",
            "description": "Cursive notes style",
            "style_model": "lstm",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "My Personal Style"
    assert data["description"] == "Cursive notes style"
    assert data["status"] == "pending"
    assert data["sample_count"] == 0
    assert "id" in data


def test_create_profile_empty_name_rejected(
    client: TestClient,
    superuser_account_token_headers: dict[str, str],
) -> None:
    response = client.post(
        f"{settings.API_V1_STR}/handwriting-profiles/",
        headers=superuser_account_token_headers,
        json={"name": "   "},
    )
    assert response.status_code == 400
    assert "Profile name cannot be empty" in response.json()["detail"]


def test_list_and_get_handwriting_profiles(
    client: TestClient,
    superuser_account_token_headers: dict[str, str],
) -> None:
    # Create two profiles
    client.post(
        f"{settings.API_V1_STR}/handwriting-profiles/",
        headers=superuser_account_token_headers,
        json={"name": "Profile Alpha"},
    )
    p2 = client.post(
        f"{settings.API_V1_STR}/handwriting-profiles/",
        headers=superuser_account_token_headers,
        json={"name": "Profile Beta"},
    ).json()

    # List profiles
    r_list = client.get(
        f"{settings.API_V1_STR}/handwriting-profiles/",
        headers=superuser_account_token_headers,
    )
    assert r_list.status_code == 200
    items = r_list.json()
    names = [p["name"] for p in items]
    assert "Profile Alpha" in names
    assert "Profile Beta" in names

    # Get single profile
    r_get = client.get(
        f"{settings.API_V1_STR}/handwriting-profiles/{p2['id']}",
        headers=superuser_account_token_headers,
    )
    assert r_get.status_code == 200
    assert r_get.json()["id"] == p2["id"]
    assert r_get.json()["name"] == "Profile Beta"


def test_update_and_delete_profile(
    client: TestClient,
    superuser_account_token_headers: dict[str, str],
) -> None:
    # Create
    created = client.post(
        f"{settings.API_V1_STR}/handwriting-profiles/",
        headers=superuser_account_token_headers,
        json={"name": "Old Name"},
    ).json()

    # Update
    r_update = client.patch(
        f"{settings.API_V1_STR}/handwriting-profiles/{created['id']}",
        headers=superuser_account_token_headers,
        json={"name": "Renamed Style", "style_model": "transformer"},
    )
    assert r_update.status_code == 200
    assert r_update.json()["name"] == "Renamed Style"
    assert r_update.json()["style_model"] == "transformer"

    # Delete
    r_del = client.delete(
        f"{settings.API_V1_STR}/handwriting-profiles/{created['id']}",
        headers=superuser_account_token_headers,
    )
    assert r_del.status_code == 200

    # Verify deleted
    r_check = client.get(
        f"{settings.API_V1_STR}/handwriting-profiles/{created['id']}",
        headers=superuser_account_token_headers,
    )
    assert r_check.status_code == 404


def test_canvas_stroke_profile(
    client: TestClient,
    superuser_account_token_headers: dict[str, str],
) -> None:
    strokes_data = "[[[10, 20], [15, 25], [20, 30]]]"
    response = client.post(
        f"{settings.API_V1_STR}/handwriting-profiles/",
        headers=superuser_account_token_headers,
        json={
            "name": "Canvas Style",
            "is_canvas_style": True,
            "canvas_strokes_json": strokes_data,
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["is_canvas_style"] is True
    assert data["status"] == "ready"


def test_canvas_stroke_point_objects_and_clear(
    client: TestClient,
    superuser_account_token_headers: dict[str, str],
) -> None:
    import json
    # Point objects captured by the interactive canvas pad
    point_strokes = [
        [{"x": 42, "y": 68}, {"x": 55, "y": 72}, {"x": 70, "y": 80}],
        [{"x": 110, "y": 95}, {"x": 125, "y": 105}]
    ]
    strokes_json = json.dumps(point_strokes)

    # 1. Create with point objects
    res_create = client.post(
        f"{settings.API_V1_STR}/handwriting-profiles/",
        headers=superuser_account_token_headers,
        json={
            "name": "Sign Off Calibration",
            "is_canvas_style": True,
            "canvas_strokes_json": strokes_json,
        },
    )
    assert res_create.status_code == 201
    profile = res_create.json()
    assert profile["is_canvas_style"] is True
    assert profile["status"] == "ready"
    assert profile["canvas_strokes_json"] == strokes_json

    # 2. Verify stored stroke points can be retrieved and parsed
    parsed = json.loads(profile["canvas_strokes_json"])
    assert len(parsed) == 2
    assert parsed[0][0]["x"] == 42

    # 3. Clear strokes via update
    res_update = client.patch(
        f"{settings.API_V1_STR}/handwriting-profiles/{profile['id']}",
        headers=superuser_account_token_headers,
        json={
            "is_canvas_style": False,
            "canvas_strokes_json": None,
            "status": "pending",
        },
    )
    assert res_update.status_code == 200
    updated = res_update.json()
    assert updated["is_canvas_style"] is False
    assert updated["canvas_strokes_json"] is None

