from __future__ import annotations

import os
import re
import uuid
from pathlib import Path
from typing import Tuple
from fastapi import HTTPException, UploadFile

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


class FileStorageService:
    def __init__(self, base_upload_dir: str = "uploads"):
        self.base_dir = Path(base_upload_dir).resolve()
        self.base_dir.mkdir(parents=True, exist_ok=True)

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
    ) -> Tuple[str, str]:
        safe_name = sanitize_filename(filename)
        unique_name = f"{uuid.uuid4().hex[:8]}_{safe_name}"
        rel_dir = Path("accounts") / str(account_id) / "profiles" / str(profile_id) / "samples"
        full_dir = (self.base_dir / rel_dir).resolve()
        full_dir.mkdir(parents=True, exist_ok=True)

        full_path = full_dir / unique_name
        full_path.write_bytes(content)

        rel_path = (rel_dir / unique_name).as_posix()
        return unique_name, rel_path

    def save_document_file(
        self,
        account_id: int,
        filename: str,
        content: bytes,
    ) -> Tuple[str, str]:
        safe_name = sanitize_filename(filename)
        unique_name = f"{uuid.uuid4().hex[:8]}_{safe_name}"
        rel_dir = Path("accounts") / str(account_id) / "documents"
        full_dir = (self.base_dir / rel_dir).resolve()
        full_dir.mkdir(parents=True, exist_ok=True)

        full_path = full_dir / unique_name
        full_path.write_bytes(content)

        rel_path = (rel_dir / unique_name).as_posix()
        return unique_name, rel_path

    def save_preview_file(
        self,
        account_id: int,
        document_id: int,
        filename: str,
        content: str | bytes,
    ) -> str:
        safe_name = sanitize_filename(filename)
        rel_dir = Path("accounts") / str(account_id) / "documents" / str(document_id)
        full_dir = (self.base_dir / rel_dir).resolve()
        full_dir.mkdir(parents=True, exist_ok=True)

        full_path = full_dir / safe_name
        if isinstance(content, str):
            full_path.write_text(content, encoding="utf-8")
        else:
            full_path.write_bytes(content)

        return (rel_dir / safe_name).as_posix()

    def get_full_path(self, rel_path: str) -> Path:
        resolved = (self.base_dir / rel_path).resolve()
        # Security check: prevent directory traversal
        if not str(resolved).startswith(str(self.base_dir)):
            raise HTTPException(status_code=400, detail="Invalid file path.")
        return resolved

    def read_file(self, rel_path: str) -> bytes:
        full = self.get_full_path(rel_path)
        if not full.is_file():
            raise HTTPException(status_code=404, detail="File not found on storage.")
        return full.read_bytes()

    def delete_file(self, rel_path: str) -> bool:
        try:
            full = self.get_full_path(rel_path)
            if full.is_file():
                full.unlink()
                return True
        except Exception:
            pass
        return False


file_storage_service = FileStorageService()
