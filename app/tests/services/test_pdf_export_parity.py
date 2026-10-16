from __future__ import annotations

import io
import re
import pypdf
import pytest

from app.services.pdf_writer import pdf_writer_service
from app.services.handwriting_engine import handwriting_engine_service, GenerationConfig


def test_pdf_geometry_and_scaling_parity_with_preview() -> None:
    """
    Verify that exported PDF ruled lines, red margin guide, and text baselines
    match the SVG preview's geometry with mathematical scaling parity.
    """
    svg_page_width = 800.0
    svg_page_height = 1100.0
    svg_margin_x = 60.0
    svg_margin_y = 80.0
    font_size = 22
    line_spacing = 1.6
    svg_line_height = font_size * line_spacing  # 35.2

    pdf_width = 612.0
    pdf_height = 792.0
    scale_x = pdf_width / svg_page_width  # 0.765
    scale_y = pdf_height / svg_page_height  # 0.720

    lines = [
        "Line 0: First sentence on notebook page.",
        "Line 1: Second sentence sitting directly on line.",
        "Line 2: Third sentence aligned with preview.",
    ]

    pdf_bytes = pdf_writer_service.generate_pdf_bytes(
        pages_lines=[lines],
        font_size=font_size,
        line_spacing=line_spacing,
        show_ruled_lines=True,
        svg_page_width=svg_page_width,
        svg_page_height=svg_page_height,
        svg_margin_x=svg_margin_x,
        svg_margin_y=svg_margin_y,
    )

    pdf_str = pdf_bytes.decode("latin-1")

    # 1. Check US Letter page dimensions
    reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
    page = reader.pages[0]
    assert float(page.mediabox.width) == 612.0
    assert float(page.mediabox.height) == 792.0

    # 2. Check Red Margin line X coordinate in PDF stream:
    # svg_margin_x - 12 = 48.0 -> 48.0 * scale_x = 36.72
    expected_margin_x = (svg_margin_x - 12.0) * scale_x
    assert f"{expected_margin_x:.2f} 0 m" in pdf_str

    # 3. Check Blue Ruled line 0 Y coordinate in PDF stream:
    # svg_ly = 80.0 -> pdf_ly = 792.0 - (80.0 * 0.72) = 734.40
    expected_ruled_y0 = pdf_height - (svg_margin_y * scale_y)
    assert f"{expected_ruled_y0:.2f} m" in pdf_str or f"{expected_ruled_y0:.2f} l" in pdf_str

    # Ruled line 1 Y:
    expected_ruled_y1 = pdf_height - ((svg_margin_y + svg_line_height) * scale_y)
    assert f"{expected_ruled_y1:.2f} m" in pdf_str or f"{expected_ruled_y1:.2f} l" in pdf_str

    # 4. Check Text Baseline 0 Y coordinate in PDF stream:
    expected_baseline_y0 = pdf_height - (svg_margin_y * scale_y)
    expected_margin_left = svg_margin_x * scale_x
    # Text line 0 must be positioned at (expected_margin_left, expected_baseline_y0)
    assert f"{expected_margin_left:.2f} {expected_baseline_y0:.2f} Td" in pdf_str


def test_hybrid_ai_and_fallback_lines_all_visible_in_pdf() -> None:
    """
    CRITICAL REGRESSION TEST:
    When a page has AI stroke vectors for the first few lines, verify that subsequent
    fallback lines are rendered VISIBLY (not invisible 3 Tr) so no lines are missing.
    """
    lines = [
        f"Paragraph sentence number {i} with distinct words to verify visibility."
        for i in range(10)
    ]

    # Mock AI stroke paths for only the first 2 lines (lines 0 and 1)
    # Each stroke is a list of points near line 0 (y ~ 80) and line 1 (y ~ 115)
    mock_vector_paths = [
        # Line 0 strokes
        [{"x": 65.0, "y": 75.0}, {"x": 70.0, "y": 80.0}, {"x": 75.0, "y": 78.0}],
        # Line 1 strokes
        [{"x": 65.0, "y": 110.0}, {"x": 70.0, "y": 115.0}, {"x": 75.0, "y": 113.0}],
    ]
    ai_line_indices = [0, 1]

    pdf_bytes = pdf_writer_service.generate_pdf_bytes(
        pages_lines=[lines],
        pages_vector_paths=[mock_vector_paths],
        pages_ai_line_indices=[ai_line_indices],
        font_size=22,
        line_spacing=1.6,
        show_ruled_lines=True,
    )

    pdf_str = pdf_bytes.decode("latin-1")

    # Lines 0 and 1 should have invisible searchable text underlay (3 Tr)
    # Lines 2 through 9 MUST have visible text (rg operator, NOT 3 Tr)
    assert "3 Tr" in pdf_str, "Vector stroke lines must have invisible searchable text underlay"
    assert "rg" in pdf_str, "Non-vector lines must have visible filled text"

    # Verify that text from lines 2 through 9 is extractable AND visible
    reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
    extracted = reader.pages[0].extract_text()
    for i in range(10):
        assert f"Paragraph sentence number {i}" in extracted, f"Line {i} must be extractable"

    # Count visible text lines in the PDF stream:
    # Lines 2..9 must be rendered with visible text color operator (rg) on content font /F1
    visible_text_matches = re.findall(r"/F1\s+[\d\.]+\s+Tf\s+[\d\.]+\s+[\d\.]+\s+[\d\.]+\s+rg\s+[\d\.]+\s+[\d\.]+\s+Td", pdf_str)
    assert len(visible_text_matches) == 8, f"Expected 8 visible fallback text lines, got {len(visible_text_matches)}"


def test_preview_approval_to_pdf_export_parity_end_to_end() -> None:
    """
    Test end-to-end preview generation through handwriting engine,
    storing preview data, and exporting to PDF with exact parity.
    """
    config = GenerationConfig(
        font_size=22,
        line_spacing=1.6,
        ink_color="#0d47a1",
        show_ruled_lines=True,
        max_ai_lines=3,
        use_ai_model=False,  # Test parameter engine to verify full font parity
    )
    text = (
        "Dear Board of Directors,\n\n"
        "We are pleased to report that the quarterly results demonstrate exceptional strength.\n"
        "Customer retention reached 98 percent while operating margins expanded significantly.\n"
        "All corporate milestones have been attained on schedule."
    )

    result = handwriting_engine_service.generate(text=text, config=config)
    assert result.total_pages >= 1
    page1 = result.pages[0]

    # Verify PagePreview contains lines and structure
    assert len(page1.lines) >= 4
    assert "<svg" in page1.svg_content

    # Export using the exact preview lines
    pdf_bytes = pdf_writer_service.generate_pdf_bytes(
        pages_lines=[page1.lines],
        font_size=config.font_size,
        line_spacing=config.line_spacing,
        ink_color=config.ink_color,
        show_ruled_lines=config.show_ruled_lines,
        pages_vector_paths=[page1.vector_paths] if page1.vector_paths else None,
        pages_ai_line_indices=[page1.ai_line_indices] if getattr(page1, "ai_line_indices", None) else None,
    )

    reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
    assert len(reader.pages) == 1
    extracted = reader.pages[0].extract_text()
    assert "Dear Board of Directors" in extracted
    assert "quarterly results" in extracted
    assert "retention reached 98 percent" in extracted
