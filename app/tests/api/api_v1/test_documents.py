import io
from fastapi.testclient import TestClient
import pypdf

from app.core.config import settings
from app.services.pdf_writer import pdf_writer_service


def _create_sample_pdf(lines: list[str]) -> bytes:
    return pdf_writer_service.generate_pdf_bytes([lines])


def _create_scanned_image_like_pdf() -> bytes:
    # A valid PDF with 1 page containing an empty content stream (no extractable text)
    return (
        b"%PDF-1.4\n"
        b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
        b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
        b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R >>\nendobj\n"
        b"4 0 obj\n<< /Length 0 >>\nstream\n\nendstream\nendobj\n"
        b"xref\n0 5\n0000000000 65535 f \n0000000009 00000 n \n0000000058 00000 n \n0000000115 00000 n \n0000000204 00000 n \n"
        b"trailer\n<< /Size 5 /Root 1 0 R >>\nstartxref\n253\n%%EOF\n"
    )


def test_upload_valid_pdf_and_extract_text(
    client: TestClient,
    superuser_account_token_headers: dict[str, str],
) -> None:
    sample_text = ["HandWriteMe Hackathon Document", "This text is digitally extracted from the uploaded PDF."]
    pdf_bytes = _create_sample_pdf(sample_text)

    response = client.post(
        f"{settings.API_V1_STR}/documents/upload",
        headers=superuser_account_token_headers,
        files={"file": ("report.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
    )
    assert response.status_code == 201
    doc = response.json()
    assert doc["filename"] == "report.pdf"
    assert doc["status"] == "extracted"
    assert doc["page_count"] == 1
    assert "HandWriteMe Hackathon Document" in doc["extracted_text"]
    assert doc["char_count"] > 0


def test_reject_scanned_pdf(
    client: TestClient,
    superuser_account_token_headers: dict[str, str],
) -> None:
    scanned_pdf_bytes = _create_scanned_image_like_pdf()

    response = client.post(
        f"{settings.API_V1_STR}/documents/upload",
        headers=superuser_account_token_headers,
        files={"file": ("scanned.pdf", io.BytesIO(scanned_pdf_bytes), "application/pdf")},
    )
    assert response.status_code == 422
    assert "Scanned or image-only PDF detected" in response.json()["detail"]


def test_reject_corrupt_and_empty_pdf(
    client: TestClient,
    superuser_account_token_headers: dict[str, str],
) -> None:
    # Empty PDF
    r_empty = client.post(
        f"{settings.API_V1_STR}/documents/upload",
        headers=superuser_account_token_headers,
        files={"file": ("empty.pdf", io.BytesIO(b""), "application/pdf")},
    )
    assert r_empty.status_code == 400

    # Non-PDF file
    r_bad = client.post(
        f"{settings.API_V1_STR}/documents/upload",
        headers=superuser_account_token_headers,
        files={"file": ("not_a_pdf.pdf", io.BytesIO(b"random text without pdf header"), "application/pdf")},
    )
    assert r_bad.status_code == 415


def test_generation_preview_approval_and_export_workflow(
    client: TestClient,
    superuser_account_token_headers: dict[str, str],
) -> None:
    # 1. Create a profile
    profile = client.post(
        f"{settings.API_V1_STR}/handwriting-profiles/",
        headers=superuser_account_token_headers,
        json={"name": "Executive Cursive", "style_model": "lstm"},
    ).json()

    # 2. Upload document
    pdf_bytes = _create_sample_pdf(["Dear Board Members,", "The quarterly results show outstanding progress."])
    doc = client.post(
        f"{settings.API_V1_STR}/documents/upload",
        headers=superuser_account_token_headers,
        files={"file": ("quarterly.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
    ).json()

    # 3. Try to approve before preview -> should fail (400)
    r_early_approve = client.post(
        f"{settings.API_V1_STR}/documents/{doc['id']}/approve",
        headers=superuser_account_token_headers,
        json={"approved": True},
    )
    assert r_early_approve.status_code == 400
    assert "valid generated preview" in r_early_approve.json()["detail"]

    # 4. Try to export before approval -> should fail (400)
    r_early_export = client.get(
        f"{settings.API_V1_STR}/documents/{doc['id']}/export",
        headers=superuser_account_token_headers,
    )
    assert r_early_export.status_code == 400
    assert "not approved for export" in r_early_export.json()["detail"]

    # 5. Generate preview
    r_gen = client.post(
        f"{settings.API_V1_STR}/documents/{doc['id']}/generate",
        headers=superuser_account_token_headers,
        json={
            "profile_id": profile["id"],
            "line_spacing": 1.6,
            "letter_spacing": 1.1,
            "ink_color": "#0d47a1",
            "randomness": 0.4,
        },
    )
    assert r_gen.status_code == 200
    gen_data = r_gen.json()
    assert gen_data["status"] == "generated"
    assert gen_data["total_pages"] >= 1
    assert "engine_mode" in gen_data
    assert "model_status_note" in gen_data
    assert "preview_svgs" in gen_data
    assert len(gen_data["preview_svgs"]) >= 1
    assert "<svg" in gen_data["preview_svgs"][0]

    # 6. Fetch preview
    r_preview = client.get(
        f"{settings.API_V1_STR}/documents/{doc['id']}/preview",
        headers=superuser_account_token_headers,
    )
    assert r_preview.status_code == 200
    preview = r_preview.json()
    assert len(preview["pages"]) >= 1
    assert "preview_svgs" in preview
    assert len(preview["preview_svgs"]) == len(preview["pages"])
    page1 = preview["pages"][0]
    assert "<svg" in page1["svg_content"]
    assert "Dear" in page1["svg_content"]
    assert "Board" in page1["svg_content"]

    # 7. Approve document
    r_approve = client.post(
        f"{settings.API_V1_STR}/documents/{doc['id']}/approve",
        headers=superuser_account_token_headers,
        json={"approved": True},
    )
    assert r_approve.status_code == 200
    approved_doc = r_approve.json()
    assert approved_doc["status"] == "approved"
    assert approved_doc["approved_at"] is not None

    # 8. Export approved document as PDF
    r_export = client.get(
        f"{settings.API_V1_STR}/documents/{doc['id']}/export",
        headers=superuser_account_token_headers,
    )
    assert r_export.status_code == 200
    assert r_export.headers["content-type"] == "application/pdf"
    assert "attachment" in r_export.headers["content-disposition"]
    
    # Verify exported PDF is valid and readable by pypdf
    exported_reader = pypdf.PdfReader(io.BytesIO(r_export.content))
    assert len(exported_reader.pages) >= 1
    extracted_from_export = exported_reader.pages[0].extract_text()
    assert "Dear Board Members" in extracted_from_export


def test_create_plain_text_document(
    client: TestClient,
    superuser_account_token_headers: dict[str, str],
) -> None:
    sample_text = "This is a clean handwritten text document created via direct text ingestion without PDFs."
    expected_words = len(sample_text.split())

    response = client.post(
        f"{settings.API_V1_STR}/documents/text",
        headers=superuser_account_token_headers,
        json={
            "title": "Meeting Minutes",
            "text": sample_text,
        },
    )
    assert response.status_code == 201
    doc = response.json()
    assert doc["id"] is not None
    assert doc["title"] == "Meeting Minutes"
    assert doc["extracted_text"] == sample_text
    assert doc["word_count"] == expected_words
    assert doc["char_count"] == len(sample_text)
    assert doc["page_count"] >= 1
    assert doc["status"] == "extracted"


def test_create_plain_text_document_root_endpoint(
    client: TestClient,
    superuser_account_token_headers: dict[str, str],
) -> None:
    text = "Testing plain text creation via the root documents post endpoint."
    response = client.post(
        f"{settings.API_V1_STR}/documents/",
        headers=superuser_account_token_headers,
        json={
            "title": "Root Endpoint Note",
            "text": text,
        },
    )
    assert response.status_code == 201
    doc = response.json()
    assert doc["title"] == "Root Endpoint Note"
    assert doc["word_count"] == len(text.split())
    assert doc["extracted_text"] == text


def test_create_plain_text_empty_rejected(
    client: TestClient,
    superuser_account_token_headers: dict[str, str],
) -> None:
    response = client.post(
        f"{settings.API_V1_STR}/documents/text",
        headers=superuser_account_token_headers,
        json={"title": "Empty Note", "text": "   "},
    )
    assert response.status_code in {400, 422}


def test_inspect_and_update_document_text(
    client: TestClient,
    superuser_account_token_headers: dict[str, str],
) -> None:
    # 1. Ingest
    initial_text = "Initial draft for handwriting conversion."
    created = client.post(
        f"{settings.API_V1_STR}/documents/text",
        headers=superuser_account_token_headers,
        json={"title": "Draft One", "text": initial_text},
    ).json()

    # 2. Inspect via GET /documents/{id}
    inspect_res = client.get(
        f"{settings.API_V1_STR}/documents/{created['id']}",
        headers=superuser_account_token_headers,
    )
    assert inspect_res.status_code == 200
    inspected = inspect_res.json()
    assert inspected["id"] == created["id"]
    assert inspected["title"] == "Draft One"
    assert inspected["extracted_text"] == initial_text
    assert inspected["word_count"] == len(initial_text.split())
    assert inspected["char_count"] == len(initial_text)

    # 3. Update text and title via PATCH /documents/{id}
    updated_text = "Revised document with significantly more detailed instructions for rendering."
    patch_res = client.patch(
        f"{settings.API_V1_STR}/documents/{created['id']}",
        headers=superuser_account_token_headers,
        json={
            "title": "Final Draft",
            "extracted_text": updated_text,
        },
    )
    assert patch_res.status_code == 200
    updated = patch_res.json()
    assert updated["title"] == "Final Draft"
    assert updated["extracted_text"] == updated_text
    assert updated["word_count"] == len(updated_text.split())
    assert updated["char_count"] == len(updated_text)

    # 4. List documents and verify updated title and word_count appear in list
    list_res = client.get(
        f"{settings.API_V1_STR}/documents/",
        headers=superuser_account_token_headers,
    )
    assert list_res.status_code == 200
    doc_in_list = next((d for d in list_res.json() if d["id"] == created["id"]), None)
    assert doc_in_list is not None
    assert doc_in_list["title"] == "Final Draft"
    assert doc_in_list["word_count"] == len(updated_text.split())


def test_generate_preview_svg_payload_and_multi_page(
    client: TestClient,
    superuser_account_token_headers: dict[str, str],
) -> None:
    # 1. Create a handwriting profile
    profile = client.post(
        f"{settings.API_V1_STR}/handwriting-profiles/",
        headers=superuser_account_token_headers,
        json={"name": "Multi-Page Author", "style_model": "svg_bezier"},
    ).json()

    # 2. Ingest a multi-page document (enough text to overflow 1 page at ~30 lines per page)
    paragraphs = [
        f"Paragraph {i}: This is comprehensive test text for multi-page handwritten document synthesis. "
        f"We ensure that SVG pages are correctly partitioned, generated, returned in preview_svgs, "
        f"and indexed so users can navigate across page 1, page 2, and beyond without missing pages."
        for i in range(1, 15)
    ]
    long_text = "\n\n".join(paragraphs)

    doc = client.post(
        f"{settings.API_V1_STR}/documents/text",
        headers=superuser_account_token_headers,
        json={"title": "Multi Page Document", "text": long_text},
    ).json()

    # 3. Generate preview with custom generation settings including slant_angle
    gen_res = client.post(
        f"{settings.API_V1_STR}/documents/{doc['id']}/generate",
        headers=superuser_account_token_headers,
        json={
            "profile_id": profile["id"],
            "slant_angle": 6.5,
            "randomness": 0.25,
            "ink_color": "#1b5e20",
            "font_size": 22,
            "line_spacing": 1.7,
        },
    )
    assert gen_res.status_code == 200
    gen_data = gen_res.json()

    # Verify response structure and fields
    assert gen_data["document_id"] == doc["id"]
    assert gen_data["status"] == "generated"
    assert gen_data["total_pages"] >= 2, f"Expected multiple pages, got {gen_data['total_pages']}"
    assert "preview_svgs" in gen_data
    assert len(gen_data["preview_svgs"]) == gen_data["total_pages"]
    assert "pages" in gen_data
    assert len(gen_data["pages"]) == gen_data["total_pages"]

    # Verify each SVG is a complete, valid SVG containing expected text and ink color
    for i, svg in enumerate(gen_data["preview_svgs"]):
        assert isinstance(svg, str)
        assert svg.strip().startswith("<svg")
        assert svg.strip().endswith("</svg>")
        assert 'xmlns="http://www.w3.org/2000/svg"' in svg
        assert "#1b5e20" in svg

    # Verify GET /documents/{id}/preview returns identical preview_svgs
    preview_res = client.get(
        f"{settings.API_V1_STR}/documents/{doc['id']}/preview",
        headers=superuser_account_token_headers,
    )
    assert preview_res.status_code == 200
    preview_data = preview_res.json()
    assert preview_data["total_pages"] == gen_data["total_pages"]
    assert "preview_svgs" in preview_data
    assert len(preview_data["preview_svgs"]) == gen_data["total_pages"]
    assert preview_data["preview_svgs"][0] == gen_data["preview_svgs"][0]


def test_generate_preview_error_cases(
    client: TestClient,
    superuser_account_token_headers: dict[str, str],
) -> None:
    # 1. Non-existent document ID -> 404
    bad_id = 999999
    r_not_found = client.post(
        f"{settings.API_V1_STR}/documents/{bad_id}/generate",
        headers=superuser_account_token_headers,
        json={"profile_id": 1, "slant_angle": 0.0},
    )
    assert r_not_found.status_code == 404

    # 2. Ingest document with empty text content -> 400
    doc = client.post(
        f"{settings.API_V1_STR}/documents/text",
        headers=superuser_account_token_headers,
        json={"title": "Blank Target", "text": "Temporary text"},
    ).json()

    # Create profile
    profile = client.post(
        f"{settings.API_V1_STR}/handwriting-profiles/",
        headers=superuser_account_token_headers,
        json={"name": "Error Tester", "style_model": "svg_bezier"},
    ).json()

    # Clear extracted_text via patch
    client.patch(
        f"{settings.API_V1_STR}/documents/{doc['id']}",
        headers=superuser_account_token_headers,
        json={"extracted_text": ""},
    )

    r_empty = client.post(
        f"{settings.API_V1_STR}/documents/{doc['id']}/generate",
        headers=superuser_account_token_headers,
        json={"profile_id": profile["id"]},
    )
    assert r_empty.status_code == 400
    assert "no text content" in r_empty.json()["detail"].lower()

    # 3. Non-existent profile_id -> 400
    # Reset valid text
    client.patch(
        f"{settings.API_V1_STR}/documents/{doc['id']}",
        headers=superuser_account_token_headers,
        json={"extracted_text": "Valid text ready for synthesis."},
    )
    r_bad_profile = client.post(
        f"{settings.API_V1_STR}/documents/{doc['id']}/generate",
        headers=superuser_account_token_headers,
        json={"profile_id": 888888},
    )
    assert r_bad_profile.status_code == 400
    assert "invalid handwriting profile" in r_bad_profile.json()["detail"].lower()


def test_approved_document_pdf_export_and_approval_gate(
    client: TestClient,
    superuser_account_token_headers: dict[str, str],
) -> None:
    # 1. Create profile and document
    profile = client.post(
        f"{settings.API_V1_STR}/handwriting-profiles/",
        headers=superuser_account_token_headers,
        json={"name": "Auditor Signature", "style_model": "svg_bezier"},
    ).json()

    paragraphs = [
        "First Section: The comprehensive annual audit confirms full regulatory compliance across all operations.",
        "Second Section: Vector handwriting geometry ensures physical print authenticity without digital distortion.",
        "Third Section: Multi-page document export correctly maintains page breaks and ruled notebook margins.",
    ]
    doc_text = "\n\n".join(paragraphs)

    doc = client.post(
        f"{settings.API_V1_STR}/documents/text",
        headers=superuser_account_token_headers,
        json={"title": "Audit Report 2026", "text": doc_text},
    ).json()

    # 2. Gate check 1: Export immediately after extraction (status == 'extracted') -> MUST 400
    r_export_unapproved_1 = client.get(
        f"{settings.API_V1_STR}/documents/{doc['id']}/export",
        headers=superuser_account_token_headers,
    )
    assert r_export_unapproved_1.status_code == 400
    assert "not approved for export" in r_export_unapproved_1.json()["detail"].lower()

    # 3. Generate preview (status becomes 'generated')
    r_gen = client.post(
        f"{settings.API_V1_STR}/documents/{doc['id']}/generate",
        headers=superuser_account_token_headers,
        json={
            "profile_id": profile["id"],
            "slant_angle": 3.0,
            "ink_color": "#0d47a1",
            "font_size": 22,
        },
    )
    assert r_gen.status_code == 200

    # 4. Gate check 2: Export after generation but BEFORE approval -> MUST 400
    r_export_unapproved_2 = client.get(
        f"{settings.API_V1_STR}/documents/{doc['id']}/export",
        headers=superuser_account_token_headers,
    )
    assert r_export_unapproved_2.status_code == 400
    assert "not approved for export" in r_export_unapproved_2.json()["detail"].lower()

    # 5. Approve document -> status becomes 'approved'
    r_approve = client.post(
        f"{settings.API_V1_STR}/documents/{doc['id']}/approve",
        headers=superuser_account_token_headers,
        json={"approved": True, "notes": "Verified for physical distribution"},
    )
    assert r_approve.status_code == 200
    assert r_approve.json()["status"] == "approved"

    # 6. Export approved document -> MUST 200 with genuine PDF
    r_export = client.get(
        f"{settings.API_V1_STR}/documents/{doc['id']}/export",
        headers=superuser_account_token_headers,
    )
    assert r_export.status_code == 200
    assert r_export.headers["content-type"] == "application/pdf"
    assert "attachment" in r_export.headers["content-disposition"]
    assert "Audit_Report_2026_handwritten.pdf" in r_export.headers["content-disposition"]

    # Verify PDF content integrity with pypdf
    pdf_reader = pypdf.PdfReader(io.BytesIO(r_export.content))
    assert len(pdf_reader.pages) >= 1
    page1 = pdf_reader.pages[0]
    
    # Check US Letter dimensions (612 x 792 pt)
    assert float(page1.mediabox.width) == 612.0
    assert float(page1.mediabox.height) == 792.0

    # Check extractable readable text
    extracted_text = page1.extract_text()
    assert "First Section" in extracted_text
    assert "comprehensive annual audit" in extracted_text

    # Verify background and ruled lines exist in raw PDF stream
    pdf_stream_content = r_export.content.decode("latin-1")
    assert "/Times-Italic" in pdf_stream_content  # Handwriting cursive font
    assert "/Helvetica" in pdf_stream_content     # Header/footer font
    assert "re f" in pdf_stream_content           # Paper background rectangle fill
    assert "RG" in pdf_stream_content             # Notebook ruled line strokes

    # 7. Gate check 3: Revoke approval -> status returns to 'generated'
    r_revoke = client.post(
        f"{settings.API_V1_STR}/documents/{doc['id']}/approve",
        headers=superuser_account_token_headers,
        json={"approved": False, "notes": "Need revision"},
    )
    assert r_revoke.status_code == 200
    assert r_revoke.json()["status"] == "generated"

    # Exporting after revocation -> MUST 400
    r_export_revoked = client.get(
        f"{settings.API_V1_STR}/documents/{doc['id']}/export",
        headers=superuser_account_token_headers,
    )
    assert r_export_revoked.status_code == 400
    assert "not approved for export" in r_export_revoked.json()["detail"].lower()




