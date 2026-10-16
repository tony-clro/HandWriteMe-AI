from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile, status
from msflib.ingestion.actions import IngestionJobAction, IngestionJobRunAction
from msflib.ingestion.models import IngestionJob, IngestionJobRunCreate, IngestionJobRunStatus, IngestionJobStatus
from sqlmodel import Session, select

from app.api import deps
from app.models import (
    Account,
    ApprovalRequest,
    Document,
    DocumentCreate,
    DocumentRead,
    DocumentTextCreate,
    DocumentUpdate,
    GenerationRequest,
    HandwritingProfile,
)
from app.services.handwriting_engine import GenerationConfig, handwriting_engine_service
from app.services.pdf_extractor import pdf_extractor_service
from app.services.pdf_writer import pdf_writer_service
from app.services.storage import file_storage_service

router = APIRouter()
job_action = IngestionJobAction()
job_run_action = IngestionJobRunAction()


@router.post("/upload", response_model=DocumentRead, status_code=status.HTTP_201_CREATED)
def upload_document(
    file: UploadFile = File(...),
    session: Session = Depends(deps.get_session),
    current_account: Account = Depends(deps.get_current_active_account),
    tenant_id: int = Depends(deps.get_current_tenant_id),
) -> Document:
    """
    Upload a PDF document, extract its text content, and track the ingestion job.
    Handles empty, invalid, and scanned (image-only) PDFs with explicit error messages.
    """
    try:
        content = file.file.read()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Failed to read uploaded file: {exc}") from exc
    finally:
        file.file.close()

    # 1. Validate PDF format
    file_storage_service.validate_pdf_bytes(content)

    # 2. Extract text using local, CPU-friendly pypdf extractor
    try:
        extraction = pdf_extractor_service.extract_text(content, filename=file.filename or "document.pdf")
    except ValueError as val_err:
        raise HTTPException(status_code=422, detail=str(val_err)) from val_err

    # 3. Store PDF file safely
    unique_name, rel_path = file_storage_service.save_document_file(
        account_id=current_account.id,
        filename=file.filename or "document.pdf",
        content=content,
    )

    # 4. Create document entity
    doc = Document(
        account_id=current_account.id,
        tenant_id=tenant_id,
        workspace_id=current_account.current_workspace_id,
        filename=file.filename or unique_name,
        storage_path=rel_path,
        size_bytes=len(content),
        extracted_text=extraction.text,
        page_count=extraction.page_count,
        char_count=extraction.char_count,
        status="extracted",
    )
    session.add(doc)
    session.commit()
    session.refresh(doc)

    # 5. Track via MSFLib IngestionJob
    try:
        job = job_action.enqueue_unique(
            session,
            subject_type="document_text_extraction",
            subject_id=str(doc.id),
            pipeline_kind="pdf_text_extraction",
            reason="create",
            tenant_id=tenant_id,
            workspace_id=current_account.current_workspace_id,
            commit=False,
        )
        job.status = IngestionJobStatus.done
        session.add(job)
        session.commit()
        session.refresh(job)

        doc.ingestion_job_id = job.id
        session.add(doc)
        session.commit()
        session.refresh(doc)
    except Exception:
        # Non-critical ingestion job tracking error does not block document creation
        pass

    return doc


@router.post("/text", response_model=DocumentRead, status_code=status.HTTP_201_CREATED)
@router.post("/", response_model=DocumentRead, status_code=status.HTTP_201_CREATED)
def create_text_document(
    payload: DocumentTextCreate,
    session: Session = Depends(deps.get_session),
    current_account: Account = Depends(deps.get_current_active_account),
    tenant_id: int = Depends(deps.get_current_tenant_id),
) -> Document:
    """
    Ingest a plain-text document directly with a title and text content.
    Persists the text file, tracks an MSFLib IngestionJob, and calculates word/char/page counts.
    """
    clean_title = (payload.title or "Untitled Document").strip()
    if not clean_title:
        clean_title = "Untitled Document"

    clean_text = (payload.text or "").strip()
    if not clean_text:
        raise HTTPException(status_code=400, detail="Document text content cannot be empty.")

    text_bytes = clean_text.encode("utf-8")
    char_count = len(clean_text)
    words = len(clean_text.split())
    lines_count = len(clean_text.splitlines())
    page_count = max(1, (lines_count + 27) // 28)

    filename = f"{clean_title}.txt" if not clean_title.lower().endswith((".txt", ".pdf")) else clean_title
    unique_name, rel_path = file_storage_service.save_document_file(
        account_id=current_account.id,
        filename=filename,
        content=text_bytes,
    )

    doc = Document(
        account_id=current_account.id,
        tenant_id=tenant_id,
        workspace_id=current_account.current_workspace_id,
        filename=clean_title,
        storage_path=rel_path,
        size_bytes=len(text_bytes),
        extracted_text=clean_text,
        page_count=page_count,
        char_count=char_count,
        status="extracted",
    )
    session.add(doc)
    session.commit()
    session.refresh(doc)

    # Track MSFLib IngestionJob
    try:
        job = job_action.enqueue_unique(
            session,
            subject_type="document_text_ingestion",
            subject_id=str(doc.id),
            pipeline_kind="plain_text_ingestion",
            reason="create",
            tenant_id=tenant_id,
            workspace_id=current_account.current_workspace_id,
            commit=False,
        )
        job.status = IngestionJobStatus.done
        session.add(job)
        session.commit()
        session.refresh(job)

        doc.ingestion_job_id = job.id
        session.add(doc)
        session.commit()
        session.refresh(doc)
    except Exception:
        pass

    return doc


@router.get("/", response_model=List[DocumentRead])
def list_documents(
    session: Session = Depends(deps.get_session),
    current_account: Account = Depends(deps.get_current_active_account),
) -> List[Document]:
    """List all documents for the current user."""
    stmt = select(Document).where(Document.account_id == current_account.id)
    if current_account.current_workspace_id is not None:
        stmt = stmt.where(
            (Document.workspace_id == current_account.current_workspace_id)
            | (Document.workspace_id == None)  # noqa: E711
        )
    return session.exec(stmt.order_by(Document.created_at.desc())).all()


@router.get("/{document_id}", response_model=DocumentRead)
def get_document(
    document_id: int,
    session: Session = Depends(deps.get_session),
    current_account: Account = Depends(deps.get_current_active_account),
) -> Document:
    """Get a document by ID."""
    doc = session.get(Document, document_id)
    if not doc or doc.account_id != current_account.id:
        raise HTTPException(status_code=404, detail="Document not found.")
    return doc


@router.patch("/{document_id}", response_model=DocumentRead)
def update_document(
    document_id: int,
    payload: DocumentUpdate,
    session: Session = Depends(deps.get_session),
    current_account: Account = Depends(deps.get_current_active_account),
) -> Document:
    """Update document text or selected profile."""
    doc = session.get(Document, document_id)
    if not doc or doc.account_id != current_account.id:
        raise HTTPException(status_code=404, detail="Document not found.")

    if payload.title is not None and payload.title.strip():
        doc.filename = payload.title.strip()

    if payload.extracted_text is not None:
        doc.extracted_text = payload.extracted_text
        doc.char_count = len(payload.extracted_text)
        lines_count = len(payload.extracted_text.splitlines())
        doc.page_count = max(1, (lines_count + 27) // 28)
        # Reset approval if text changed
        doc.approved_at = None
        if doc.status == "approved":
            doc.status = "generated"

    if payload.selected_profile_id is not None:
        profile = session.get(HandwritingProfile, payload.selected_profile_id)
        if not profile or profile.account_id != current_account.id:
            raise HTTPException(status_code=400, detail="Selected profile does not exist or not authorized.")
        doc.selected_profile_id = payload.selected_profile_id

    session.add(doc)
    session.commit()
    session.refresh(doc)
    return doc


@router.delete("/{document_id}", status_code=status.HTTP_200_OK)
def delete_document(
    document_id: int,
    session: Session = Depends(deps.get_session),
    current_account: Account = Depends(deps.get_current_active_account),
) -> dict:
    """Delete a document and any generated previews or files."""
    doc = session.get(Document, document_id)
    if not doc or doc.account_id != current_account.id:
        raise HTTPException(status_code=404, detail="Document not found.")

    if doc.storage_path:
        file_storage_service.delete_file(doc.storage_path)
    if doc.preview_path:
        file_storage_service.delete_file(doc.preview_path)
    if doc.export_path:
        file_storage_service.delete_file(doc.export_path)

    session.delete(doc)
    session.commit()
    return {"message": "Document deleted successfully.", "id": document_id}


# --- GENERATION & PREVIEW ---

@router.post("/{document_id}/generate", status_code=status.HTTP_200_OK)
def generate_preview(
    document_id: int,
    payload: GenerationRequest,
    session: Session = Depends(deps.get_session),
    current_account: Account = Depends(deps.get_current_active_account),
    tenant_id: int = Depends(deps.get_current_tenant_id),
) -> dict:
    """
    Generate handwriting preview for the document using the selected handwriting profile.
    Supports adjustable font size, line spacing, letter spacing, ink color, and randomness.
    """
    doc = session.get(Document, document_id)
    if not doc or doc.account_id != current_account.id:
        raise HTTPException(status_code=404, detail="Document not found.")

    if not doc.extracted_text or not doc.extracted_text.strip():
        raise HTTPException(status_code=400, detail="Document has no text content to render.")

    profile = session.get(HandwritingProfile, payload.profile_id)
    if not profile or profile.account_id != current_account.id:
        raise HTTPException(status_code=400, detail="Invalid handwriting profile specified.")

    doc.status = "generating"
    doc.selected_profile_id = profile.id
    session.add(doc)
    session.commit()

    # Track generation with IngestionJob
    job_id = None
    try:
        job = job_action.enqueue_unique(
            session,
            subject_type="handwriting_generation",
            subject_id=str(doc.id),
            pipeline_kind="handwriting_synthesis",
            reason="generate",
            tenant_id=tenant_id,
            workspace_id=current_account.current_workspace_id,
            commit=True,
        )
        job_id = job.id
    except Exception:
        pass

    # Execute handwriting generation locally
    config = GenerationConfig(
        font_size=payload.font_size,
        line_spacing=payload.line_spacing,
        letter_spacing=payload.letter_spacing,
        ink_color=payload.ink_color,
        randomness=payload.randomness,
        slant_angle=payload.slant_angle,
    )

    try:
        engine_result = handwriting_engine_service.generate(
            text=doc.extracted_text,
            profile_name=profile.name,
            style_model=profile.style_model,
            is_canvas_style=profile.is_canvas_style,
            canvas_strokes_json=profile.canvas_strokes_json,
            config=config,
        )
    except Exception as exc:
        doc.status = "failed"
        doc.error_message = f"Generation failed: {exc}"
        session.add(doc)
        if job_id:
            try:
                j = job_action.get(session, job_id)
                if j:
                    j.status = IngestionJobStatus.failed
                    j.error = str(exc)
                    session.add(j)
            except Exception:
                pass
        session.commit()
        raise HTTPException(status_code=500, detail=f"Generation engine error: {exc}") from exc

    # Persist preview data
    pages_list = [
        {
            "page_number": p.page_number,
            "svg_content": p.svg_content,
            "lines_count": p.lines_count,
            "word_count": p.word_count,
            "lines": getattr(p, "lines", []),
            "vector_paths": getattr(p, "vector_paths", []),
            "ai_line_indices": getattr(p, "ai_line_indices", []),
        }
        for p in engine_result.pages
    ]
    svgs_list = [p.svg_content for p in engine_result.pages]

    preview_data = {
        "engine_mode": engine_result.engine_mode,
        "model_status_note": engine_result.model_status_note,
        "total_pages": engine_result.total_pages,
        "total_lines": engine_result.total_lines,
        "total_words": engine_result.total_words,
        "total_chars": engine_result.total_chars,
        "profile_name": profile.name,
        "ink_color": config.ink_color,
        "font_size": config.font_size,
        "line_spacing": config.line_spacing,
        "margin_x": config.margin_x,
        "margin_y": config.margin_y,
        "page_width": config.page_width,
        "page_height": config.page_height,
        "show_ruled_lines": config.show_ruled_lines,
        "pages": pages_list,
    }

    preview_json = json.dumps(preview_data)

    preview_rel_path = file_storage_service.save_preview_file(
        account_id=current_account.id,
        document_id=doc.id,
        filename="preview.json",
        content=preview_json,
    )

    doc.preview_data_json = preview_json
    doc.preview_path = preview_rel_path
    doc.status = "generated"
    doc.error_message = None
    doc.approved_at = None  # Requires re-approval upon new generation
    session.add(doc)

    # Mark ingestion job done
    if job_id:
        try:
            j = job_action.get(session, job_id)
            if j:
                j.status = IngestionJobStatus.done
                session.add(j)
        except Exception:
            pass

    session.commit()
    session.refresh(doc)

    return {
        "document_id": doc.id,
        "status": doc.status,
        "total_pages": engine_result.total_pages,
        "engine_mode": engine_result.engine_mode,
        "model_status_note": engine_result.model_status_note,
        "preview_url": f"/api/v1/documents/{doc.id}/preview",
        "preview_svgs": svgs_list,
        "pages": pages_list,
    }


@router.get("/{document_id}/preview")
def get_document_preview(
    document_id: int,
    session: Session = Depends(deps.get_session),
    current_account: Account = Depends(deps.get_current_active_account),
) -> dict:
    """Retrieve the generated preview data and page SVGs for the document."""
    doc = session.get(Document, document_id)
    if not doc or doc.account_id != current_account.id:
        raise HTTPException(status_code=404, detail="Document not found.")

    if not doc.preview_data_json:
        raise HTTPException(
            status_code=400,
            detail="No preview has been generated yet for this document. Call /generate first.",
        )

    try:
        data = json.loads(doc.preview_data_json)
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Failed to load preview data.") from exc

    data["document_id"] = doc.id
    data["document_status"] = doc.status
    data["is_approved"] = doc.status == "approved"
    data["approved_at"] = doc.approved_at.isoformat() if doc.approved_at else None
    data["preview_svgs"] = [p["svg_content"] for p in data.get("pages", []) if "svg_content" in p]
    return data


# --- APPROVAL & EXPORT ---

@router.post("/{document_id}/approve", response_model=DocumentRead)
def approve_document(
    document_id: int,
    payload: ApprovalRequest,
    session: Session = Depends(deps.get_session),
    current_account: Account = Depends(deps.get_current_active_account),
) -> Document:
    """
    Approve the document for export.
    Approval is strictly separated from generation and requires an existing generated preview.
    """
    doc = session.get(Document, document_id)
    if not doc or doc.account_id != current_account.id:
        raise HTTPException(status_code=404, detail="Document not found.")

    if not doc.preview_data_json or doc.status not in ("generated", "approved"):
        raise HTTPException(
            status_code=400,
            detail="Document must have a valid generated preview before it can be approved.",
        )

    if not payload.approved:
        # User rejects / revokes approval
        doc.status = "generated"
        doc.approved_at = None
    else:
        doc.status = "approved"
        doc.approved_at = datetime.now(timezone.utc)

    session.add(doc)
    session.commit()
    session.refresh(doc)
    return doc


@router.get("/{document_id}/export")
def export_document_pdf(
    document_id: int,
    session: Session = Depends(deps.get_session),
    current_account: Account = Depends(deps.get_current_active_account),
) -> Response:
    """
    Download the approved document as a genuine PDF file.
    Only approved documents with existing previews can be exported.
    """
    doc = session.get(Document, document_id)
    if not doc or doc.account_id != current_account.id:
        raise HTTPException(status_code=404, detail="Document not found.")

    if doc.status != "approved" or not doc.approved_at:
        raise HTTPException(
            status_code=400,
            detail="Document is not approved for export. Please review and approve the document first.",
        )

    if not doc.extracted_text and not doc.preview_data_json:
        raise HTTPException(status_code=400, detail="Document contains no text to export.")

    # Retrieve lines, style, profile, ink color, geometry, and vector paths from existing preview data if available
    pages_lines: List[List[str]] = []
    pages_vector_paths: List[List[List[dict]]] = []
    pages_ai_line_indices: List[List[int]] = []
    profile_name = "HandWriteMe"
    ink_color = "#1a237e"
    font_size = 22
    line_spacing = 1.6
    margin_x = 60.0
    margin_y = 80.0
    page_width = 800.0
    page_height = 1100.0
    show_ruled_lines = True

    if doc.preview_data_json:
        try:
            preview_data = json.loads(doc.preview_data_json)
            profile_name = preview_data.get("profile_name", profile_name)
            ink_color = preview_data.get("ink_color", ink_color)
            font_size = preview_data.get("font_size", font_size)
            line_spacing = float(preview_data.get("line_spacing", line_spacing))
            margin_x = float(preview_data.get("margin_x", margin_x))
            margin_y = float(preview_data.get("margin_y", margin_y))
            page_width = float(preview_data.get("page_width", page_width))
            page_height = float(preview_data.get("page_height", page_height))
            show_ruled_lines = preview_data.get("show_ruled_lines", True)
            raw_pages = preview_data.get("pages", [])
            for page_dict in raw_pages:
                lines = page_dict.get("lines")
                if lines:
                    pages_lines.append(lines)
                vp = page_dict.get("vector_paths")
                pages_vector_paths.append(vp if vp else [])
                ai_indices = page_dict.get("ai_line_indices", [])
                pages_ai_line_indices.append(ai_indices)
        except Exception:
            pages_lines = []
            pages_vector_paths = []
            pages_ai_line_indices = []

    if not pages_lines and doc.extracted_text:
        pages_lines = pdf_writer_service.wrap_text_into_pages(doc.extracted_text)

    if not pages_lines:
        pages_lines = [[""]]

    has_any_vectors = any(bool(vp) for vp in pages_vector_paths)
    has_any_indices = any(bool(idx) for idx in pages_ai_line_indices)

    pdf_bytes = pdf_writer_service.generate_pdf_bytes(
        pages_lines=pages_lines,
        title=f"HandWriteMe - {doc.filename}",
        profile_name=profile_name,
        ink_color=ink_color,
        font_size=font_size,
        line_spacing=line_spacing,
        show_ruled_lines=show_ruled_lines,
        pages_vector_paths=pages_vector_paths if has_any_vectors else None,
        pages_ai_line_indices=pages_ai_line_indices if has_any_indices else None,
        svg_page_width=page_width,
        svg_page_height=page_height,
        svg_margin_x=margin_x,
        svg_margin_y=margin_y,
    )

    clean_stem = doc.filename.rsplit(".", 1)[0].strip().replace(" ", "_")
    out_filename = f"{clean_stem}_handwritten.pdf"


    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{out_filename}"',
        },
    )

