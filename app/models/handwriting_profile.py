from __future__ import annotations

from datetime import datetime
from typing import Optional
from msflib.models.base import ModelBase, SchemaBase
from sqlmodel import Field


class HandwritingProfile(ModelBase, table=True):
    name: str = Field(index=True, max_length=255)
    description: Optional[str] = Field(default=None, max_length=1024)
    status: str = Field(default="pending", max_length=50)  # pending, ready, calibrated, failed
    style_model: str = Field(default="lstm", max_length=50)  # lstm, transformer, synthesis
    is_canvas_style: bool = Field(default=False)
    canvas_strokes_json: Optional[str] = Field(default=None)
    sample_count: int = Field(default=0)
    
    account_id: int = Field(index=True, foreign_key="account.id")
    tenant_id: int = Field(index=True, foreign_key="tenant.id")
    workspace_id: Optional[int] = Field(default=None, index=True, foreign_key="workspace.id")


class HandwritingProfileCreate(SchemaBase):
    name: str
    description: Optional[str] = None
    style_model: str = "lstm"
    is_canvas_style: bool = False
    canvas_strokes_json: Optional[str] = None


class HandwritingProfileUpdate(SchemaBase):
    name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    style_model: Optional[str] = None
    is_canvas_style: Optional[bool] = None
    canvas_strokes_json: Optional[str] = None


class HandwritingProfileRead(SchemaBase):
    id: int
    name: str
    description: Optional[str] = None
    status: str
    style_model: str
    is_canvas_style: bool
    canvas_strokes_json: Optional[str] = None
    sample_count: int
    account_id: int
    tenant_id: int
    workspace_id: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
