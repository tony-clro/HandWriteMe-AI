from __future__ import annotations

import logging
import os
import re
import uuid
from pathlib import Path
from typing import Any, Tuple
from fastapi import HTTPException

from app.core.config import settings

logger = logging.getLogger("app.services.storage")

ALLOWED_IMAGE_TYPES = {
    "image/png": [b"\x89PNG\r\n\x1a\n"],
    "image/jpeg": [b"\xff\xd8\xff"],
    "image/webp": [b"RIFF"],
}

ALLOWED_PDF_TYPES = {
    "application/pdf": [b"%PDF-"],
}

MAX_IMAGE_BYTES = 10 * 1024 * 1024  # 10 MB
MAX_PDF_BYTES = 25 * 1024 * 1024    # 25 MB


def sanitize_filename(filename: str | None) -> str:
    if not filename:
        return f"file_{uuid.uuid4().hex[:8]}"
    # Remove directory separators and unsafe characters
    cleaned = Path(filename).name
    cleaned = re.sub(r"[^\w\.-]", "_", cleaned)
    if not cleaned or cleaned.startswith("."):
        cleaned = f"file_{uuid.uuid4().hex[:8]}{cleaned}"
    return cleaned[:100]


def _validate_storage_key(key: str) -> str:
    """Validate and sanitize storage key to prevent directory traversal in both local and S3 storage."""
    if not key or not str(key).strip():
        raise HTTPException(status_code=400, detail="Invalid storage path: empty path.")
    cleaned = str(key).strip().replace("\\", "/").lstrip("/")
    parts = cleaned.split("/")
    if ".." in parts or not cleaned:
        raise HTTPException(status_code=400, detail="Invalid storage path: directory traversal not allowed.")
    return cleaned


class FileStorageService:
    """Storage service supporting both local filesystem storage and S3-compatible object storage (Cloudflare R2).

    - STORAGE_METHOD=file: persists to local directory (default).
    - STORAGE_METHOD=s3: persists to S3/Cloudflare R2 via boto3 without public buckets or URLs.
    """

    def __init__(
        self,
        base_upload_dir: str = "uploads",
        storage_method: str | None = None,
        bucket_name: str | None = None,
        aws_access_key_id: str | None = None,
        aws_secret_access_key: str | None = None,
        aws_region: str | None = None,
        endpoint_url: str | None = None,
        s3_client: Any = None,
    ):
        raw_method = (
            storage_method
            or os.getenv("STORAGE_METHOD")
            or getattr(settings, "STORAGE_METHOD", None)
            or "file"
        )
        self.storage_method = str(raw_method).strip().lower()

        if self.storage_method == "s3":
            self.bucket_name = (
                bucket_name
                or os.getenv("STORAGE_BUCKET_NAME")
                or getattr(settings, "STORAGE_BUCKET_NAME", None)
                or ""
            ).strip()
            self.aws_access_key_id = (
                aws_access_key_id
                or os.getenv("AWS_ACCESS_KEY_ID")
                or getattr(settings, "AWS_ACCESS_KEY_ID", None)
                or ""
            ).strip()
            self.aws_secret_access_key = (
                aws_secret_access_key
                or os.getenv("AWS_SECRET_ACCESS_KEY")
                or getattr(settings, "AWS_SECRET_ACCESS_KEY", None)
                or ""
            ).strip()
            self.aws_region = (
                aws_region
                or os.getenv("AWS_S3_REGION")
                or getattr(settings, "AWS_S3_REGION", None)
                or "auto"
            ).strip()
            self.endpoint_url = (
                endpoint_url
                or os.getenv("AWS_ENDPOINT_URL_S3")
                or os.getenv("AWS_ENDPOINT_URL")
                or getattr(settings, "AWS_ENDPOINT_URL_S3", None)
                or ""
            ).strip() or None

            # Fail clearly when required configuration is missing in S3 mode
            if not self.bucket_name:
                raise ValueError("STORAGE_BUCKET_NAME is required when STORAGE_METHOD is 's3'.")
            if not self.aws_access_key_id or not self.aws_secret_access_key:
                raise ValueError(
                    "AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY are required when STORAGE_METHOD is 's3'."
                )

            if s3_client is not None:
                self.s3_client = s3_client
            else:
                import boto3

                boto3_kwargs: dict[str, Any] = {
                    "service_name": "s3",
                    "aws_access_key_id": self.aws_access_key_id,
                    "aws_secret_access_key": self.aws_secret_access_key,
                    "region_name": self.aws_region or "auto",
                }
                if self.endpoint_url:
                    boto3_kwargs["endpoint_url"] = self.endpoint_url
                self.s3_client = boto3.client(**boto3_kwargs)

            self.base_dir = None
        else:
            self.storage_method = "file"
            self.base_dir = Path(base_upload_dir).resolve()
            self.base_dir.mkdir(parents=True, exist_ok=True)
            self.s3_client = None
            self.bucket_name = None

    def _s3_put(self, key: str, content: bytes, content_type: str | None = None) -> None:
        """Internal helper to put an object to S3-compatible storage."""
        from botocore.exceptions import BotoCoreError, ClientError

        clean_key = _validate_storage_key(key)
        put_kwargs: dict[str, Any] = {
            "Bucket": self.bucket_name,
            "Key": clean_key,
            "Body": content,
        }
        if content_type:
            put_kwargs["ContentType"] = content_type

        try:
            self.s3_client.put_object(**put_kwargs)
        except (ClientError, BotoCoreError, Exception) as exc:
            logger.error("S3 upload failed for key '%s': %s", clean_key, exc)
            raise HTTPException(status_code=500, detail=f"S3 upload error: {exc}") from exc

    def _s3_get(self, key: str) -> bytes:
        """Internal helper to get an object from S3-compatible storage."""
        from botocore.exceptions import BotoCoreError, ClientError

        clean_key = _validate_storage_key(key)
        try:
            response = self.s3_client.get_object(Bucket=self.bucket_name, Key=clean_key)
            body = response.get("Body")
            if body is None:
                raise HTTPException(status_code=404, detail="File not found on storage.")
            return body.read()
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code")
            if code in ("NoSuchKey", "NotFound", "404"):
                raise HTTPException(status_code=404, detail="File not found on storage.") from exc
            logger.error("S3 read failed for key '%s': %s", clean_key, exc)
            raise HTTPException(status_code=500, detail=f"S3 read error: {exc}") from exc
        except (BotoCoreError, Exception) as exc:
            logger.error("S3 read failed for key '%s': %s", clean_key, exc)
            raise HTTPException(status_code=500, detail=f"Storage read error: {exc}") from exc

    def _s3_delete(self, key: str) -> bool:
        """Internal helper to delete an object from S3-compatible storage."""
        try:
            clean_key = _validate_storage_key(key)
            self.s3_client.delete_object(Bucket=self.bucket_name, Key=clean_key)
            return True
        except Exception as exc:
            logger.error("S3 delete failed for key '%s': %s", key, exc)
            return False

    def validate_image_bytes(self, content: bytes, declared_type: str | None = None) -> str:
        if not content or len(content) == 0:
            raise HTTPException(status_code=400, detail="Uploaded file is empty.")
        if len(content) > MAX_IMAGE_BYTES:
            raise HTTPException(
                status_code=413,
                detail=f"File exceeds maximum allowed size of {MAX_IMAGE_BYTES // (1024 * 1024)}MB.",
            )

        # Validate header signatures
        detected_type = None
        for mime, sigs in ALLOWED_IMAGE_TYPES.items():
            for sig in sigs:
                if content.startswith(sig):
                    if mime == "image/webp" and len(content) > 12 and content[8:12] != b"WEBP":
                        continue
                    detected_type = mime
                    break
            if detected_type:
                break

        if not detected_type:
            raise HTTPException(
                status_code=415,
                detail="Unsupported image format. Allowed formats: PNG, JPEG, WEBP.",
            )

        return detected_type

    def validate_pdf_bytes(self, content: bytes) -> None:
        if not content or len(content) == 0:
            raise HTTPException(status_code=400, detail="Uploaded PDF is empty.")
        if len(content) > MAX_PDF_BYTES:
            raise HTTPException(
                status_code=413,
                detail=f"PDF exceeds maximum allowed size of {MAX_PDF_BYTES // (1024 * 1024)}MB.",
            )
        if not content.startswith(b"%PDF-"):
            raise HTTPException(
                status_code=415,
                detail="Uploaded file is not a valid PDF (invalid magic header).",
            )

    def save_sample_file(
        self,
        account_id: int,
        profile_id: int,
        filename: str,
        content: bytes,
        content_type: str | None = None,
    ) -> Tuple[str, str]:
        safe_name = sanitize_filename(filename)
        unique_name = f"{uuid.uuid4().hex[:8]}_{safe_name}"
        rel_path = f"accounts/{account_id}/profiles/{profile_id}/samples/{unique_name}"

        if self.storage_method == "s3":
            ct = content_type or "image/png"
            self._s3_put(rel_path, content, content_type=ct)
        else:
            full_dir = (self.base_dir / Path(rel_path).parent).resolve()
            full_dir.mkdir(parents=True, exist_ok=True)
            full_path = self.base_dir / rel_path
            full_path.write_bytes(content)

        return unique_name, rel_path

    def save_document_file(
        self,
        account_id: int,
        filename: str,
        content: bytes,
        content_type: str | None = None,
    ) -> Tuple[str, str]:
        safe_name = sanitize_filename(filename)
        unique_name = f"{uuid.uuid4().hex[:8]}_{safe_name}"
        rel_path = f"accounts/{account_id}/documents/{unique_name}"

        if self.storage_method == "s3":
            if not content_type:
                if content.startswith(b"%PDF-"):
                    content_type = "application/pdf"
                else:
                    content_type = "application/octet-stream"
            self._s3_put(rel_path, content, content_type=content_type)
        else:
            full_dir = (self.base_dir / Path(rel_path).parent).resolve()
            full_dir.mkdir(parents=True, exist_ok=True)
            full_path = self.base_dir / rel_path
            full_path.write_bytes(content)

        return unique_name, rel_path

    def save_preview_file(
        self,
        account_id: int,
        document_id: int,
        filename: str,
        content: str | bytes,
    ) -> str:
        safe_name = sanitize_filename(filename)
        rel_path = f"accounts/{account_id}/documents/{document_id}/{safe_name}"

        if isinstance(content, str):
            content_bytes = content.encode("utf-8")
        else:
            content_bytes = content

        if self.storage_method == "s3":
            self._s3_put(rel_path, content_bytes, content_type="application/json")
        else:
            full_dir = (self.base_dir / Path(rel_path).parent).resolve()
            full_dir.mkdir(parents=True, exist_ok=True)
            full_path = self.base_dir / rel_path
            full_path.write_bytes(content_bytes)

        return rel_path

    def get_full_path(self, rel_path: str) -> Path:
        """Resolve a storage key to an absolute local Path. Only available in local file storage mode."""
        if self.storage_method != "file":
            raise HTTPException(
                status_code=501,
                detail="Local filesystem path is not available when using S3 storage mode.",
            )
        clean_key = _validate_storage_key(rel_path)
        resolved = (self.base_dir / clean_key).resolve()
        # Security check: prevent directory traversal
        if not str(resolved).startswith(str(self.base_dir)):
            raise HTTPException(status_code=400, detail="Invalid file path: path traversal detected.")
        return resolved

    def read_file(self, rel_path: str) -> bytes:
        clean_key = _validate_storage_key(rel_path)
        if self.storage_method == "s3":
            return self._s3_get(clean_key)
        else:
            full = self.get_full_path(clean_key)
            if not full.is_file():
                raise HTTPException(status_code=404, detail="File not found on storage.")
            return full.read_bytes()

    def delete_file(self, rel_path: str) -> bool:
        try:
            clean_key = _validate_storage_key(rel_path)
        except HTTPException:
            return False

        if self.storage_method == "s3":
            return self._s3_delete(clean_key)
        else:
            try:
                full = self.get_full_path(clean_key)
                if full.is_file():
                    full.unlink()
                    return True
            except Exception:
                pass
            return False


file_storage_service = FileStorageService()

