import io
from fastapi.testclient import TestClient

from app.core.config import settings

# 1x1 valid PNG bytes
VALID_PNG_BYTES = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06"
    b"\x00\x00\x00\x1f\x15c4\x00\x00\x00\rIDATx\x9cc`\x00\x00\x00\x02\x00\x01H\xaf"
    b"\xa4q\x00\x00\x00\x00IEND\xaeB`\x82"
)

# 1x1 valid JPEG bytes
VALID_JPEG_BYTES = (
    b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00H\x00H\x00\x00\xff\xdb\x00C\x00"
    b"\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19"
    b"\x12\x13\x0f\x14\x1d\x1a\x1f\x1e\x1d\x1a\x1c\x1c $.' \",#\x1c\x1c(7),01444\x1f'9=82<.342\xff"
    b"\xc0\x00\x0b\x08\x00\x01\x00\x01\x01\x01\x11\x00\xff\xc4\x00\x1f\x00\x00\x01\x05\x01\x01\x01"
    b"\x01\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x01\x02\x03\x04\x05\x06\x07\x08\t\n\x0b\xff\xda"
    b"\x00\x08\x01\x01\x00\x00?\x00\xbf\x00\xff\xd9"
)


def test_upload_sample_image_and_list(
    client: TestClient,
    superuser_account_token_headers: dict[str, str],
) -> None:
    # 1. Create a profile
    profile = client.post(
        f"{settings.API_V1_STR}/handwriting-profiles/",
        headers=superuser_account_token_headers,
        json={"name": "Sample Test Profile"},
    ).json()

    assert profile["sample_count"] == 0
    assert profile["status"] == "pending"

    # 2. Upload valid PNG sample
    response = client.post(
        f"{settings.API_V1_STR}/handwriting-profiles/{profile['id']}/samples",
        headers=superuser_account_token_headers,
        files={"file": ("sample.png", io.BytesIO(VALID_PNG_BYTES), "image/png")},
        data={"label": "Sample Sentence"},
    )
    assert response.status_code == 201
    sample = response.json()
    assert sample["profile_id"] == profile["id"]
    assert sample["content_type"] == "image/png"
    assert sample["label"] == "Sample Sentence"
    assert sample["size_bytes"] == len(VALID_PNG_BYTES)

    # 3. Check profile status is now ready and sample_count is 1
    updated_profile = client.get(
        f"{settings.API_V1_STR}/handwriting-profiles/{profile['id']}",
        headers=superuser_account_token_headers,
    ).json()
    assert updated_profile["sample_count"] == 1
    assert updated_profile["status"] == "ready"

    # 4. List samples
    r_list = client.get(
        f"{settings.API_V1_STR}/handwriting-profiles/{profile['id']}/samples",
        headers=superuser_account_token_headers,
    )
    assert r_list.status_code == 200
    samples = r_list.json()
    assert len(samples) == 1
    assert samples[0]["id"] == sample["id"]

    # 5. Stream sample file
    r_file = client.get(
        f"{settings.API_V1_STR}/handwriting-profiles/{profile['id']}/samples/{sample['id']}/file",
        headers=superuser_account_token_headers,
    )
    assert r_file.status_code == 200
    assert r_file.headers["content-type"] == "image/png"
    assert r_file.content == VALID_PNG_BYTES

    # 6. Delete sample
    r_del = client.delete(
        f"{settings.API_V1_STR}/handwriting-profiles/{profile['id']}/samples/{sample['id']}",
        headers=superuser_account_token_headers,
    )
    assert r_del.status_code == 200

    # 7. Check sample count decremented
    refreshed_profile = client.get(
        f"{settings.API_V1_STR}/handwriting-profiles/{profile['id']}",
        headers=superuser_account_token_headers,
    ).json()
    assert refreshed_profile["sample_count"] == 0
    assert refreshed_profile["status"] == "pending"


def test_reject_invalid_sample_files(
    client: TestClient,
    superuser_account_token_headers: dict[str, str],
) -> None:
    profile = client.post(
        f"{settings.API_V1_STR}/handwriting-profiles/",
        headers=superuser_account_token_headers,
        json={"name": "Rejection Test Profile"},
    ).json()

    # Empty file
    r_empty = client.post(
        f"{settings.API_V1_STR}/handwriting-profiles/{profile['id']}/samples",
        headers=superuser_account_token_headers,
        files={"file": ("empty.png", io.BytesIO(b""), "image/png")},
    )
    assert r_empty.status_code == 400

    # Fake PNG (plain text disguised as PNG)
    r_fake = client.post(
        f"{settings.API_V1_STR}/handwriting-profiles/{profile['id']}/samples",
        headers=superuser_account_token_headers,
        files={"file": ("fake.png", io.BytesIO(b"This is just text, not an image"), "image/png")},
    )
    assert r_fake.status_code == 415
    assert "Unsupported image format" in r_fake.json()["detail"]
