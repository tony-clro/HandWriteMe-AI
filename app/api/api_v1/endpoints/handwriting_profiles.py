from __future__ import annotations

import json
from typing import List, Optional
from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile, status
from sqlmodel import Session, select

from app.actions import (
    handwriting_profile_action,
    handwriting_sample_action,
)
from app.api import deps
from app.models import (
    Account,
    HandwritingProfile,
    HandwritingProfileCreate,
    HandwritingProfileRead,
    HandwritingProfileUpdate,
    HandwritingSample,
    HandwritingSampleCreate,
    HandwritingSampleRead,
)
from app.services.storage import file_storage_service

router = APIRouter()


@router.post("/", response_model=HandwritingProfileRead, status_code=status.HTTP_201_CREATED)
def create_profile(
    payload: HandwritingProfileCreate,
    session: Session = Depends(deps.get_session),
    current_account: Account = Depends(deps.get_current_active_account),
    tenant_id: int = Depends(deps.get_current_tenant_id),
) -> HandwritingProfile:
    """Create a new handwriting profile associated with the authenticated account and tenant."""
    if not payload.name or not payload.name.strip():
        raise HTTPException(status_code=400, detail="Profile name cannot be empty.")

    profile = HandwritingProfile(
        name=payload.name.strip(),
        description=payload.description.strip() if payload.description else None,
        style_model=payload.style_model,
        is_canvas_style=payload.is_canvas_style,
        canvas_strokes_json=payload.canvas_strokes_json,
        status="ready" if payload.is_canvas_style and payload.canvas_strokes_json else "pending",
        sample_count=0,
        account_id=current_account.id,
        tenant_id=tenant_id,
        workspace_id=current_account.current_workspace_id,
    )
    session.add(profile)
    session.commit()
    session.refresh(profile)
    return profile


@router.get("/", response_model=List[HandwritingProfileRead])
def list_profiles(
    session: Session = Depends(deps.get_session),
    current_account: Account = Depends(deps.get_current_active_account),
) -> List[HandwritingProfile]:
    """List all handwriting profiles belonging to the current user."""
    stmt = select(HandwritingProfile).where(
        HandwritingProfile.account_id == current_account.id
    )
    if current_account.current_workspace_id is not None:
        stmt = stmt.where(
            (HandwritingProfile.workspace_id == current_account.current_workspace_id)
            | (HandwritingProfile.workspace_id == None)  # noqa: E711
        )
    return session.exec(stmt.order_by(HandwritingProfile.created_at.desc())).all()


@router.get("/{profile_id}", response_model=HandwritingProfileRead)
def get_profile(
    profile_id: int,
    session: Session = Depends(deps.get_session),
    current_account: Account = Depends(deps.get_current_active_account),
) -> HandwritingProfile:
    """Retrieve a handwriting profile by ID."""
    profile = session.get(HandwritingProfile, profile_id)
    if not profile or profile.account_id != current_account.id:
        raise HTTPException(status_code=404, detail="Handwriting profile not found.")
    return profile


@router.patch("/{profile_id}", response_model=HandwritingProfileRead)
def update_profile(
    profile_id: int,
    payload: HandwritingProfileUpdate,
    session: Session = Depends(deps.get_session),
    current_account: Account = Depends(deps.get_current_active_account),
) -> HandwritingProfile:
    """Update profile details (name, description, canvas strokes, style model)."""
    profile = session.get(HandwritingProfile, profile_id)
    if not profile or profile.account_id != current_account.id:
        raise HTTPException(status_code=404, detail="Handwriting profile not found.")

    update_data = payload.model_dump(exclude_unset=True)

    if "name" in update_data:
        val = update_data["name"]
        if not val or not val.strip():
            raise HTTPException(status_code=400, detail="Profile name cannot be empty.")
        profile.name = val.strip()

    if "description" in update_data:
        val = update_data["description"]
        profile.description = val.strip() if val else None

    if "style_model" in update_data:
        profile.style_model = update_data["style_model"]

    if "is_canvas_style" in update_data:
        profile.is_canvas_style = update_data["is_canvas_style"]

    if "canvas_strokes_json" in update_data:
        profile.canvas_strokes_json = update_data["canvas_strokes_json"]
        if profile.canvas_strokes_json and profile.status == "pending":
            profile.status = "ready"
        elif not profile.canvas_strokes_json and profile.status == "ready" and profile.sample_count == 0:
            profile.status = "pending"

    if "status" in update_data:
        profile.status = update_data["status"]

    session.add(profile)
    session.commit()
    session.refresh(profile)
    return profile


@router.delete("/{profile_id}", status_code=status.HTTP_200_OK)
def delete_profile(
    profile_id: int,
    session: Session = Depends(deps.get_session),
    current_account: Account = Depends(deps.get_current_active_account),
) -> dict:
    """Delete a handwriting profile and its associated samples."""
    profile = session.get(HandwritingProfile, profile_id)
    if not profile or profile.account_id != current_account.id:
        raise HTTPException(status_code=404, detail="Handwriting profile not found.")

    # Delete sample files and records
    samples = session.exec(
        select(HandwritingSample).where(HandwritingSample.profile_id == profile_id)
    ).all()
    for sample in samples:
        file_storage_service.delete_file(sample.storage_path)
        session.delete(sample)

    session.delete(profile)
    session.commit()
    return {"message": "Profile and associated samples deleted successfully.", "id": profile_id}


# --- SAMPLES MANAGEMENT ---

@router.post("/{profile_id}/samples", response_model=HandwritingSampleRead, status_code=status.HTTP_201_CREATED)
def upload_sample(
    profile_id: int,
    file: UploadFile = File(...),
    label: Optional[str] = Form(default=None),
    session: Session = Depends(deps.get_session),
    current_account: Account = Depends(deps.get_current_active_account),
    tenant_id: int = Depends(deps.get_current_tenant_id),
) -> HandwritingSample:
    """Upload a handwriting sample image for the profile."""
    profile = session.get(HandwritingProfile, profile_id)
    if not profile or profile.account_id != current_account.id:
        raise HTTPException(status_code=404, detail="Handwriting profile not found.")

    # Read and validate content
    try:
        content = file.file.read()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Failed to read file: {exc}") from exc
    finally:
        file.file.close()

    detected_mime = file_storage_service.validate_image_bytes(content, file.content_type)
    
    unique_name, rel_path = file_storage_service.save_sample_file(
        account_id=current_account.id,
        profile_id=profile_id,
        filename=file.filename or "sample.png",
        content=content,
    )

    sample = HandwritingSample(
        profile_id=profile_id,
        account_id=current_account.id,
        tenant_id=tenant_id,
        workspace_id=current_account.current_workspace_id,
        filename=file.filename or unique_name,
        storage_path=rel_path,
        content_type=detected_mime,
        size_bytes=len(content),
        label=label.strip() if label else None,
        is_processed=True,
    )
    session.add(sample)

    # Update profile sample count and mark ready
    profile.sample_count += 1
    if profile.status == "pending":
        profile.status = "ready"
    session.add(profile)

    session.commit()
    session.refresh(sample)
    return sample


@router.get("/{profile_id}/samples", response_model=List[HandwritingSampleRead])
def list_samples(
    profile_id: int,
    session: Session = Depends(deps.get_session),
    current_account: Account = Depends(deps.get_current_active_account),
) -> List[HandwritingSample]:
    """List all samples uploaded for a profile."""
    profile = session.get(HandwritingProfile, profile_id)
    if not profile or profile.account_id != current_account.id:
        raise HTTPException(status_code=404, detail="Handwriting profile not found.")

    samples = session.exec(
        select(HandwritingSample)
        .where(HandwritingSample.profile_id == profile_id)
        .order_by(HandwritingSample.created_at.desc())
    ).all()
    return samples


@router.delete("/{profile_id}/samples/{sample_id}", status_code=status.HTTP_200_OK)
def delete_sample(
    profile_id: int,
    sample_id: int,
    session: Session = Depends(deps.get_session),
    current_account: Account = Depends(deps.get_current_active_account),
) -> dict:
    """Delete a specific handwriting sample."""
    profile = session.get(HandwritingProfile, profile_id)
    if not profile or profile.account_id != current_account.id:
        raise HTTPException(status_code=404, detail="Handwriting profile not found.")

    sample = session.get(HandwritingSample, sample_id)
    if not sample or sample.profile_id != profile_id or sample.account_id != current_account.id:
        raise HTTPException(status_code=404, detail="Sample not found.")

    file_storage_service.delete_file(sample.storage_path)
    session.delete(sample)

    profile.sample_count = max(0, profile.sample_count - 1)
    if profile.sample_count == 0 and not profile.canvas_strokes_json:
        profile.status = "pending"
    session.add(profile)

    session.commit()
    return {"message": "Sample deleted successfully.", "sample_id": sample_id}


@router.get("/{profile_id}/samples/{sample_id}/file")
def get_sample_file(
    profile_id: int,
    sample_id: int,
    token: Optional[str] = None,
    session: Session = Depends(deps.get_session),
    current_account: Optional[Account] = Depends(deps.get_current_account_or_none),
) -> Response:
    """Stream sample image content, accepting Bearer header or token query parameter."""
    account = current_account
    if not account and token:
        from msflib.auth.deps import ALGORITHM, TokenPayload, jwt
        from app.core.config import settings
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
            token_data = TokenPayload(**payload)
            account = session.exec(
                select(Account).where(Account.email == token_data.sub)
            ).first()
        except Exception:
            raise HTTPException(status_code=401, detail="Could not validate credentials")

    if not account:
        raise HTTPException(status_code=401, detail="Not authenticated")

    sample = session.get(HandwritingSample, sample_id)
    if not sample or sample.profile_id != profile_id or sample.account_id != account.id:
        raise HTTPException(status_code=404, detail="Sample not found.")

    file_bytes = file_storage_service.read_file(sample.storage_path)
    return Response(content=file_bytes, media_type=sample.content_type)

