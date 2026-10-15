from __future__ import annotations

import io
from unittest.mock import MagicMock
from botocore.exceptions import ClientError
from botocore.response import StreamingBody
import pytest
from fastapi import HTTPException

from app.services.storage import FileStorageService, sanitize_filename


def test_sanitize_filename() -> None:
    assert sanitize_filename("my sample (1).png") == "my_sample__1_.png"
    assert sanitize_filename("../../../etc/passwd") == "passwd"
    assert sanitize_filename("")[:5] == "file_"


def test_file_mode_local_crud(tmp_path) -> None:
    """Verifies that local filesystem mode works properly for save, read, and delete."""
    svc = FileStorageService(base_upload_dir=str(tmp_path), storage_method="file")
    assert svc.storage_method == "file"
    assert svc.base_dir is not None

    sample_bytes = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
    unique_name, rel_path = svc.save_sample_file(
        account_id=1,
        profile_id=42,
        filename="test.png",
        content=sample_bytes,
    )
    assert rel_path == f"accounts/1/profiles/42/samples/{unique_name}"
    assert (tmp_path / rel_path).is_file()

    # Read file
    content = svc.read_file(rel_path)
    assert content == sample_bytes

    # Local path resolution
    full_path = svc.get_full_path(rel_path)
    assert full_path.is_file()

    # Delete file
    deleted = svc.delete_file(rel_path)
    assert deleted is True
    assert not (tmp_path / rel_path).exists()

    # Reading deleted file raises 404
    with pytest.raises(HTTPException) as exc_info:
        svc.read_file(rel_path)
    assert exc_info.value.status_code == 404


def test_file_mode_path_traversal_protection(tmp_path) -> None:
    """Verifies that directory traversal attacks are rejected with 400."""
    svc = FileStorageService(base_upload_dir=str(tmp_path), storage_method="file")

    with pytest.raises(HTTPException) as exc_info:
        svc.read_file("../../outside.txt")
    assert exc_info.value.status_code == 400
    assert "Invalid storage path" in exc_info.value.detail

    with pytest.raises(HTTPException) as exc_info:
        svc.get_full_path("../../../etc/shadow")
    assert exc_info.value.status_code == 400


def test_s3_mode_missing_config_raises_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """S3 mode fails clearly when required bucket or credentials are missing."""
    monkeypatch.delenv("STORAGE_BUCKET_NAME", raising=False)
    monkeypatch.delenv("AWS_ACCESS_KEY_ID", raising=False)
    monkeypatch.delenv("AWS_SECRET_ACCESS_KEY", raising=False)

    # Missing bucket name
    with pytest.raises(ValueError, match="STORAGE_BUCKET_NAME is required"):
        FileStorageService(
            storage_method="s3",
            bucket_name="",
            aws_access_key_id="test_key",
            aws_secret_access_key="test_secret",
        )

    # Missing credentials
    with pytest.raises(ValueError, match="AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY are required"):
        FileStorageService(
            storage_method="s3",
            bucket_name="my-bucket",
            aws_access_key_id="",
            aws_secret_access_key="",
        )


def test_s3_mode_get_full_path_raises_501() -> None:
    """Local filesystem path resolution is explicitly rejected in S3 mode."""
    mock_s3 = MagicMock()
    svc = FileStorageService(
        storage_method="s3",
        bucket_name="my-r2-bucket",
        aws_access_key_id="dummy_key",
        aws_secret_access_key="dummy_secret",
        aws_region="auto",
        s3_client=mock_s3,
    )
    with pytest.raises(HTTPException) as exc_info:
        svc.get_full_path("accounts/1/documents/doc.pdf")
    assert exc_info.value.status_code == 501
    assert "not available when using S3 storage mode" in exc_info.value.detail


def test_s3_mode_save_sample_file() -> None:
    """save_sample_file puts object into S3 bucket with correct hierarchical key and ContentType."""
    mock_s3 = MagicMock()
    svc = FileStorageService(
        storage_method="s3",
        bucket_name="test-r2-bucket",
        aws_access_key_id="dummy_key",
        aws_secret_access_key="dummy_secret",
        aws_region="auto",
        s3_client=mock_s3,
    )

    image_data = b"\x89PNG\r\n\x1a\nfakeimage"
    unique_name, rel_path = svc.save_sample_file(
        account_id=7,
        profile_id=15,
        filename="handwriting.png",
        content=image_data,
        content_type="image/png",
    )

    expected_key = f"accounts/7/profiles/15/samples/{unique_name}"
    assert rel_path == expected_key
    mock_s3.put_object.assert_called_once_with(
        Bucket="test-r2-bucket",
        Key=expected_key,
        Body=image_data,
        ContentType="image/png",
    )


def test_s3_mode_save_document_and_preview_files() -> None:
    """save_document_file and save_preview_file put objects into S3 with correct keys."""
    mock_s3 = MagicMock()
    svc = FileStorageService(
        storage_method="s3",
        bucket_name="test-r2-bucket",
        aws_access_key_id="dummy_key",
        aws_secret_access_key="dummy_secret",
        aws_region="auto",
        s3_client=mock_s3,
    )

    # 1. Document file
    pdf_bytes = b"%PDF-1.4 simulated pdf"
    doc_name, doc_path = svc.save_document_file(
        account_id=2,
        filename="contract.pdf",
        content=pdf_bytes,
    )
    assert doc_path == f"accounts/2/documents/{doc_name}"
    mock_s3.put_object.assert_any_call(
        Bucket="test-r2-bucket",
        Key=doc_path,
        Body=pdf_bytes,
        ContentType="application/pdf",
    )

    # 2. Preview file
    preview_json = '{"pages": []}'
    prev_path = svc.save_preview_file(
        account_id=2,
        document_id=99,
        filename="preview.json",
        content=preview_json,
    )
    assert prev_path == "accounts/2/documents/99/preview.json"
    mock_s3.put_object.assert_any_call(
        Bucket="test-r2-bucket",
        Key="accounts/2/documents/99/preview.json",
        Body=preview_json.encode("utf-8"),
        ContentType="application/json",
    )


def test_s3_mode_read_file_success() -> None:
    """read_file fetches the object stream from S3 and returns bytes."""
    mock_s3 = MagicMock()
    content_bytes = b"Hello from S3 Object"
    stream = StreamingBody(io.BytesIO(content_bytes), len(content_bytes))
    mock_s3.get_object.return_value = {"Body": stream}

    svc = FileStorageService(
        storage_method="s3",
        bucket_name="test-r2-bucket",
        aws_access_key_id="dummy_key",
        aws_secret_access_key="dummy_secret",
        aws_region="auto",
        s3_client=mock_s3,
    )

    result = svc.read_file("accounts/5/documents/file.txt")
    assert result == content_bytes
    mock_s3.get_object.assert_called_once_with(
        Bucket="test-r2-bucket",
        Key="accounts/5/documents/file.txt",
    )


def test_s3_mode_read_file_not_found() -> None:
    """read_file maps S3 NoSuchKey to HTTP 404."""
    mock_s3 = MagicMock()
    error_response = {"Error": {"Code": "NoSuchKey", "Message": "The specified key does not exist."}}
    mock_s3.get_object.side_effect = ClientError(error_response, "GetObject")

    svc = FileStorageService(
        storage_method="s3",
        bucket_name="test-r2-bucket",
        aws_access_key_id="dummy_key",
        aws_secret_access_key="dummy_secret",
        aws_region="auto",
        s3_client=mock_s3,
    )

    with pytest.raises(HTTPException) as exc_info:
        svc.read_file("accounts/5/documents/missing.txt")
    assert exc_info.value.status_code == 404
    assert "File not found on storage" in exc_info.value.detail


def test_s3_mode_read_file_server_error() -> None:
    """read_file maps generic S3 errors to HTTP 500 without falling back to local filesystem."""
    mock_s3 = MagicMock()
    error_response = {"Error": {"Code": "InternalError", "Message": "S3 failure."}}
    mock_s3.get_object.side_effect = ClientError(error_response, "GetObject")

    svc = FileStorageService(
        storage_method="s3",
        bucket_name="test-r2-bucket",
        aws_access_key_id="dummy_key",
        aws_secret_access_key="dummy_secret",
        aws_region="auto",
        s3_client=mock_s3,
    )

    with pytest.raises(HTTPException) as exc_info:
        svc.read_file("accounts/5/documents/doc.pdf")
    assert exc_info.value.status_code == 500
    assert "S3 read error" in exc_info.value.detail


def test_s3_mode_delete_file() -> None:
    """delete_file issues delete_object to S3."""
    mock_s3 = MagicMock()
    svc = FileStorageService(
        storage_method="s3",
        bucket_name="test-r2-bucket",
        aws_access_key_id="dummy_key",
        aws_secret_access_key="dummy_secret",
        aws_region="auto",
        s3_client=mock_s3,
    )

    success = svc.delete_file("accounts/10/profiles/3/samples/abc_sample.png")
    assert success is True
    mock_s3.delete_object.assert_called_once_with(
        Bucket="test-r2-bucket",
        Key="accounts/10/profiles/3/samples/abc_sample.png",
    )


def test_s3_mode_sample_upload_and_stream_api(
    client,
    superuser_account_token_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verifies that API endpoints seamlessly upload, stream, and delete files when S3 mode is active."""
    from app.core.config import settings
    import app.services.storage as storage_mod
    import app.api.api_v1.endpoints.handwriting_profiles as hp_endpoints
    import app.api.api_v1.endpoints.documents as doc_endpoints

    s3_store: dict[str, bytes] = {}

    def fake_put_object(**kwargs):
        s3_store[kwargs["Key"]] = kwargs["Body"]
        return {"ETag": '"mock-etag"'}

    def fake_get_object(**kwargs):
        key = kwargs["Key"]
        if key not in s3_store:
            raise ClientError({"Error": {"Code": "NoSuchKey"}}, "GetObject")
        data = s3_store[key]
        return {"Body": StreamingBody(io.BytesIO(data), len(data))}

    def fake_delete_object(**kwargs):
        s3_store.pop(kwargs["Key"], None)
        return {}

    mock_s3 = MagicMock()
    mock_s3.put_object.side_effect = fake_put_object
    mock_s3.get_object.side_effect = fake_get_object
    mock_s3.delete_object.side_effect = fake_delete_object

    s3_service = FileStorageService(
        storage_method="s3",
        bucket_name="r2-production-bucket",
        aws_access_key_id="mock_id",
        aws_secret_access_key="mock_secret",
        aws_region="auto",
        endpoint_url="https://account_id.r2.cloudflarestorage.com",
        s3_client=mock_s3,
    )

    # Monkeypatch the singleton in the modules
    monkeypatch.setattr(storage_mod, "file_storage_service", s3_service)
    monkeypatch.setattr(hp_endpoints, "file_storage_service", s3_service)
    monkeypatch.setattr(doc_endpoints, "file_storage_service", s3_service)

    # 1. Create Profile
    profile_res = client.post(
        f"{settings.API_V1_STR}/handwriting-profiles/",
        headers=superuser_account_token_headers,
        json={"name": "S3 Profile Test"},
    )
    assert profile_res.status_code == 201
    profile = profile_res.json()

    # 2. Upload Sample to S3 via API
    png_bytes = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06"
        b"\x00\x00\x00\x1f\x15c4\x00\x00\x00\rIDATx\x9cc`\x00\x00\x00\x02\x00\x01H\xaf"
        b"\xa4q\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    upload_res = client.post(
        f"{settings.API_V1_STR}/handwriting-profiles/{profile['id']}/samples",
        headers=superuser_account_token_headers,
        files={"file": ("handwriting.png", io.BytesIO(png_bytes), "image/png")},
        data={"label": "S3 Sample"},
    )
    assert upload_res.status_code == 201
    sample = upload_res.json()
    assert len(s3_store) == 1
    uploaded_key = list(s3_store.keys())[0]
    assert uploaded_key.startswith("accounts/")
    assert s3_store[uploaded_key] == png_bytes

    # 3. Stream File from S3 via API
    stream_res = client.get(
        f"{settings.API_V1_STR}/handwriting-profiles/{profile['id']}/samples/{sample['id']}/file",
        headers=superuser_account_token_headers,
    )
    assert stream_res.status_code == 200
    assert stream_res.content == png_bytes

    # 4. Delete Sample from S3 via API
    del_res = client.delete(
        f"{settings.API_V1_STR}/handwriting-profiles/{profile['id']}/samples/{sample['id']}",
        headers=superuser_account_token_headers,
    )
    assert del_res.status_code == 200
    assert uploaded_key not in s3_store
