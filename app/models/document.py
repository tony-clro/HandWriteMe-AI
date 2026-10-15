from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from msflib.models.base import ModelBase, SchemaBase
from pydantic import model_validator
from sqlalchemy import Column, DateTime
from sqlmodel import Field


class Document(ModelBase, table=True):
    account_id: int = Field(index=True, foreign_key="account.id")
    tenant_id: int = Field(index=True, foreign_key="tenant.id")
    workspace_id: Optional[int] = Field(default=None, index=True, foreign_key="workspace.id")

    filename: str = Field(max_length=255)
    storage_path: str = Field(max_length=1024)
    size_bytes: int = Field(default=0)

    extracted_text: Optional[str] = Field(default=None)
    page_count: int = Field(default=0)
    char_count: int = Field(default=0)

    status: str = Field(default="uploaded", max_length=50)  # uploaded, extracted, generating, generated, approved, failed
    error_message: Optional[str] = Field(default=None, max_length=2048)

    selected_profile_id: Optional[int] = Field(default=None, foreign_key="handwritingprofile.id")
    preview_data_json: Optional[str] = Field(default=None)
    preview_path: Optional[str] = Field(default=None, max_length=1024)
    export_path: Optional[str] = Field(default=None, max_length=1024)
    
    ingestion_job_id: Optional[int] = Field(default=None, index=True)

    approved_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )


class DocumentCreate(SchemaBase):
    filename: str
    storage_path: str
    size_bytes: int
    extracted_text: Optional[str] = None
    page_count: int = 0
    char_count: int = 0
    status: str = "uploaded"


class DocumentTextCreate(SchemaBase):
    title: str = Field(default="Untitled Document", min_length=1, max_length=255)
    text: str = Field(min_length=1)


class DocumentUpdate(SchemaBase):
    title: Optional[str] = None
    extracted_text: Optional[str] = None
    word_count: Optional[int] = None
    selected_profile_id: Optional[int] = None
    status: Optional[str] = None
    error_message: Optional[str] = None
    preview_data_json: Optional[str] = None
    preview_path: Optional[str] = None
    export_path: Optional[str] = None
    approved_at: Optional[datetime] = None


class DocumentRead(SchemaBase):
    id: int
    account_id: int
    tenant_id: int
    workspace_id: Optional[int] = None
    filename: str
    size_bytes: int
    extracted_text: Optional[str] = None
    page_count: int
    char_count: int
    status: str
    error_message: Optional[str] = None
    selected_profile_id: Optional[int] = None
    preview_path: Optional[str] = None
    export_path: Optional[str] = None
    ingestion_job_id: Optional[int] = None
    approved_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    title: Optional[str] = None
    word_count: int = 0

    @model_validator(mode="before")
    @classmethod
    def populate_derived_fields(cls, data: Any) -> Any:
        if hasattr(data, "__dict__"):
            text = getattr(data, "extracted_text", None) or ""
            fname = getattr(data, "filename", "") or "Untitled Document"
            words = len(text.strip().split()) if text.strip() else 0
            clean_title = fname.rsplit(".", 1)[0] if "." in fname else fname
            d = {k: getattr(data, k, None) for k in cls.model_fields.keys() if k not in ("title", "word_count")}
            d["word_count"] = words
            d["title"] = clean_title or "Untitled Document"
            return d
        elif isinstance(data, dict):
            text = data.get("extracted_text") or ""
            fname = data.get("filename") or "Untitled Document"
            words = len(text.strip().split()) if text.strip() else 0
            clean_title = fname.rsplit(".", 1)[0] if "." in fname else fname
            data["word_count"] = data.get("word_count") if data.get("word_count") is not None else words
            data["title"] = data.get("title") or clean_title or "Untitled Document"
            return data
        return data


class GenerationRequest(SchemaBase):
    profile_id: int
    line_spacing: float = 1.5
    letter_spacing: float = 1.0
    ink_color: str = "#1a237e"  # Deep blue ink
    randomness: float = 0.5
    font_size: int = 24
    slant_angle: float = 0.0


class ApprovalRequest(SchemaBase):
    approved: bool = True
    notes: Optional[str] = None
