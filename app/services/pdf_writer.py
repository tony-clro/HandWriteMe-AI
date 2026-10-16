from __future__ import annotations

import io
from typing import List, Optional, Tuple


def hex_to_rgb(hex_str: str) -> Tuple[float, float, float]:
    """Convert hex color string (e.g. #1a237e) to 0.0-1.0 RGB tuple."""
    clean = hex_str.lstrip("#")
    if len(clean) == 6:
        try:
            return (
                int(clean[0:2], 16) / 255.0,
                int(clean[2:4], 16) / 255.0,
                int(clean[4:6], 16) / 255.0,
            )
        except ValueError:
            pass
    return (0.102, 0.137, 0.494)


class PDFWriterService:
    """
    Standard, compliant PDF writer for generating downloadable PDF documents from generated text.
    Produces valid multi-page PDF 1.4 files without external cloud or C dependencies.
    Renders notebook ruled lines, margin guides, and handwriting geometry matching the preview.
    """

    @staticmethod
    def wrap_text_into_pages(
        text: str,
        chars_per_line: int = 56,
        lines_per_page: int = 26,
    ) -> List[List[str]]:
        """Cleanly wrap raw text into structured pages and lines without splitting words."""
        raw_paragraphs = text.replace("\r\n", "\n").split("\n")
        wrapped_lines: List[str] = []
        for para in raw_paragraphs:
            para = para.strip()
            if not para:
                wrapped_lines.append("")
                continue
            words = para.split(" ")
            current_line = ""
            for word in words:
                candidate = f"{current_line} {word}".strip() if current_line else word
                if len(candidate) <= chars_per_line:
                    current_line = candidate
                else:
                    if current_line:
                        wrapped_lines.append(current_line)
                    current_line = word
            if current_line:
                wrapped_lines.append(current_line)

        if not wrapped_lines:
            wrapped_lines = [""]

        pages: List[List[str]] = []
        cur_page: List[str] = []
        for line in wrapped_lines:
            if len(cur_page) >= lines_per_page:
                pages.append(cur_page)
                cur_page = []
            cur_page.append(line)
        if cur_page or not pages:
            pages.append(cur_page)
        return pages

    @staticmethod
    def generate_pdf_bytes(
        pages_lines: List[List[str]],
        title: str = "HandWriteMe Generated Document",
        profile_name: str = "HandWriteMe",
        font_size: int = 22,
        line_height: Optional[float] = None,
        line_spacing: float = 1.6,
        ink_color: str = "#1a237e",
        show_ruled_lines: bool = True,
        pages_vector_paths: Optional[List[List[List[dict]]]] = None,
        pages_ai_line_indices: Optional[List[List[int]]] = None,
        svg_page_width: float = 800.0,
        svg_page_height: float = 1100.0,
        svg_margin_x: float = 60.0,
        svg_margin_y: float = 80.0,
    ) -> bytes:
        # Standard US Letter dimensions (612 x 792 pt, 8.5 x 11 in)
        page_width = 612
        page_height = 792

        # Scale factors mapping SVG coordinates (default 800 x 1100) to US Letter (612 x 792)
        scale_x = page_width / float(svg_page_width)
        scale_y = page_height / float(svg_page_height)

        # SVG line geometry matching handwriting engine
        if font_size > 18:
            svg_line_height = float(font_size) * float(line_spacing)
            pdf_font_size = max(11, int(round(font_size * scale_y)))
        else:
            # Backwards compatibility when scaled font_size (e.g. 14) is passed directly
            pdf_font_size = font_size
            svg_line_height = (line_height / scale_y) if line_height else (22.0 * line_spacing)

        usable_height = svg_page_height - (svg_margin_y * 2)
        lines_per_page = max(5, int(usable_height / svg_line_height))

        ink_r, ink_g, ink_b = hex_to_rgb(ink_color)

        total_pages = max(1, len(pages_lines))
        page_obj_ids = [7 + (2 * i) for i in range(total_pages)]

        objects = {}

        # 1. Catalog
        objects[1] = b"<< /Type /Catalog /Pages 3 0 R >>"

        # 2. Outlines
        objects[2] = b"<< /Type /Outlines /Count 0 >>"

        # 3. Pages tree
        kids_str = " ".join(f"{pid} 0 R" for pid in page_obj_ids)
        objects[3] = f"<< /Type /Pages /Kids [{kids_str}] /Count {total_pages} >>".encode("ascii")

        # 4. Base-14 Handwriting Font (Times-Italic for cursive manuscript look)
        objects[4] = b"<< /Type /Font /Subtype /Type1 /BaseFont /Times-Italic >>"

        # 5. Base-14 Clean Font (Helvetica for header/footer)
        objects[5] = b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"

        # For each page, create Content Stream and Page Object
        for i in range(total_pages):
            lines = pages_lines[i] if i < len(pages_lines) else []
            stream_parts: List[str] = []

            # 1. Soft notebook paper background (#fbf9f4)
            stream_parts.append(f"q 0.984 0.976 0.957 rg 0 0 {page_width} {page_height} re f Q")

            # 2. Ruled lines & red left margin guide matching preview geometry precisely
            if show_ruled_lines:
                # Vertical red margin line
                margin_line_x = (svg_margin_x - 12.0) * scale_x
                stream_parts.append(
                    f"q 0.949 0.545 0.510 RG 0.92 w {margin_line_x:.2f} 0 m {margin_line_x:.2f} {page_height} l S Q"
                )

                # Horizontal blue ruled notebook lines matching preview positions
                x_start = max(18.0, (svg_margin_x - 20.0) * scale_x)
                x_end = min(page_width - 18.0, (svg_page_width - svg_margin_x + 20.0) * scale_x)
                for l_idx in range(lines_per_page + 1):
                    svg_ly = svg_margin_y + (l_idx * svg_line_height)
                    pdf_ly = page_height - (svg_ly * scale_y)
                    if 0 <= pdf_ly <= page_height:
                        stream_parts.append(
                            f"q 0.761 0.820 0.878 RG 0.60 w {x_start:.2f} {pdf_ly:.2f} m {x_end:.2f} {pdf_ly:.2f} l S Q"
                        )

            # Check if genuine vector stroke paths exist for this page
            page_vectors = (
                pages_vector_paths[i]
                if pages_vector_paths and i < len(pages_vector_paths) and pages_vector_paths[i]
                else None
            )

            # Track which lines have vector strokes
            ai_line_indices: set[int] = set()
            if pages_ai_line_indices and i < len(pages_ai_line_indices) and pages_ai_line_indices[i]:
                ai_line_indices = set(pages_ai_line_indices[i])

            if page_vectors:
                # 3a. Genuine AI Vector Stroke Paths rendered natively in PDF
                for seg in page_vectors:
                    if len(seg) < 2:
                        continue
                    x0 = seg[0]["x"] * scale_x
                    y0 = page_height - (seg[0]["y"] * scale_y)
                    path_tokens = [f"{x0:.2f} {y0:.2f} m"]
                    for pt in seg[1:]:
                        px = pt["x"] * scale_x
                        py = page_height - (pt["y"] * scale_y)
                        path_tokens.append(f"{px:.2f} {py:.2f} l")
                    stream_parts.append(
                        f"q {ink_r:.3f} {ink_g:.3f} {ink_b:.3f} RG 1.35 w 1 J 1 j "
                        + " ".join(path_tokens)
                        + " S Q"
                    )

            # 3b. Text lines:
            # - For lines with AI vector strokes: render invisible searchable text (rendering mode 3 Tr)
            #   at the exact baseline so text extraction, screen readers, and search work seamlessly.
            # - For lines without vector strokes (fallback / parameter lines): render visible text (mode 0 rg)
            #   so NO lines are missing or invisible in the exported PDF.
            pdf_margin_left = svg_margin_x * scale_x
            for l_idx, line in enumerate(lines):
                if not line:
                    continue

                svg_baseline = svg_margin_y + (l_idx * svg_line_height)
                pdf_baseline = page_height - (svg_baseline * scale_y)

                safe = (
                    line.replace("\\", "\\\\")
                    .replace("(", "\\(")
                    .replace(")", "\\)")
                )
                ascii_safe = safe.encode("ascii", "replace").decode("ascii")

                # Determine if this specific line was rendered with vector strokes
                line_has_vectors = False
                if ai_line_indices:
                    line_has_vectors = l_idx in ai_line_indices
                elif page_vectors:
                    # Backward compatibility fallback: check segment proximity
                    line_has_vectors = any(
                        abs(seg[0]["y"] - svg_baseline) < (svg_line_height * 0.75)
                        for seg in page_vectors
                        if seg
                    )

                if line_has_vectors:
                    # Invisible searchable text underlay (mode 3 Tr: neither fill nor stroke)
                    stream_parts.append(
                        f"BT /F1 {pdf_font_size} Tf 3 Tr {pdf_margin_left:.2f} {pdf_baseline:.2f} Td ({ascii_safe}) Tj ET"
                    )
                else:
                    # Visible text in ink color sitting directly on the ruled baseline
                    stream_parts.append(
                        f"BT /F1 {pdf_font_size} Tf {ink_r:.3f} {ink_g:.3f} {ink_b:.3f} rg "
                        f"{pdf_margin_left:.2f} {pdf_baseline:.2f} Td ({ascii_safe}) Tj ET"
                    )

            # 4. Page footer with page number and profile name
            footer_text = f"Page {i + 1} of {total_pages}" + (f" - {profile_name}" if profile_name else "")
            safe_footer = (
                footer_text.replace("\\", "\\\\")
                .replace("(", "\\(")
                .replace(")", "\\)")
                .encode("ascii", "replace")
                .decode("ascii")
            )
            footer_x = max(36.0, (page_width // 2) - (len(safe_footer) * 2.8))
            footer_y = max(16.0, page_height - (1075.0 * scale_y))
            stream_parts.append(
                f"BT /F2 8.5 Tf 0.5 0.5 0.5 rg {footer_x:.1f} {footer_y:.1f} Td ({safe_footer}) Tj ET"
            )

            stream_content = "\n".join(stream_parts).encode("latin-1")

            content_id = 6 + (2 * i)
            page_id = 7 + (2 * i)

            # Content stream object
            objects[content_id] = (
                f"<< /Length {len(stream_content)} >>\nstream\n".encode("ascii")
                + stream_content
                + b"\nendstream"
            )

            # Page object
            objects[page_id] = (
                f"<< /Type /Page /Parent 3 0 R "
                f"/MediaBox [0 0 {page_width} {page_height}] "
                f"/Resources << /Font << /F1 4 0 R /F2 5 0 R >> >> "
                f"/Contents {content_id} 0 R >>".encode("ascii")
            )

        # Build xref table and final PDF file
        output = io.BytesIO()
        output.write(b"%PDF-1.4\n")

        offsets = {}
        for obj_id in sorted(objects.keys()):
            offsets[obj_id] = output.tell()
            output.write(f"{obj_id} 0 obj\n".encode("ascii"))
            output.write(objects[obj_id])
            output.write(b"\nendobj\n")

        xref_pos = output.tell()
        num_objects = max(objects.keys()) + 1
        output.write(f"xref\n0 {num_objects}\n".encode("ascii"))
        output.write(b"0000000000 65535 f \n")
        for obj_id in range(1, num_objects):
            offset = offsets.get(obj_id, 0)
            output.write(f"{offset:010d} 00000 n \n".encode("ascii"))

        output.write(
            f"trailer\n<< /Size {num_objects} /Root 1 0 R >>\n"
            f"startxref\n{xref_pos}\n%%EOF\n".encode("ascii")
        )

        return output.getvalue()


pdf_writer_service = PDFWriterService()

