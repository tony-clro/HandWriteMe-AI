from __future__ import annotations

from datetime import datetime
from typing import Optional
from msflib.models.base import ModelBase, SchemaBase
from sqlmodel import Field


class HandwritingSample(ModelBase, table=True):
    profile_id: int = Field(index=True, foreign_key="handwritingprofile.id")
    account_id: int = Field(index=True, foreign_key="account.id")
    tenant_id: int = Field(index=True, foreign_key="tenant.id")
    workspace_id: Optional[int] = Field(default=None, index=True, foreign_key="workspace.id")
    
    filename: str = Field(max_length=255)
    storage_path: str = Field(max_length=1024)
    content_type: str = Field(max_length=128)
    size_bytes: int = Field(default=0)
    label: Optional[str] = Field(default=None, max_length=100)
    is_processed: bool = Field(default=False)


class HandwritingSampleCreate(SchemaBase):
    profile_id: int
    filename: str
    storage_path: str
    content_type: str
    size_bytes: int
    label: Optional[str] = None


class HandwritingSampleRead(SchemaBase):
    id: int
    profile_id: int
    account_id: int
    tenant_id: int
    workspace_id: Optional[int] = None
    filename: str
    content_type: str
    size_bytes: int
    label: Optional[str] = None
    is_processed: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
