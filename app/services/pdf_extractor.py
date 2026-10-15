from __future__ import annotations

import io
from dataclasses import dataclass
from typing import List, Optional
import pypdf
from pypdf.errors import PdfReadError


@dataclass
class ExtractedPage:
    page_number: int
    text: str
    char_count: int


@dataclass
class PDFExtractionResult:
    text: str
    page_count: int
    char_count: int
    pages: List[ExtractedPage]


class PDFExtractorService:
    @staticmethod
    def extract_text(file_bytes: bytes, filename: str = "document.pdf") -> PDFExtractionResult:
        if not file_bytes or len(file_bytes) == 0:
            raise ValueError(f"Uploaded file '{filename}' is empty (0 bytes).")

        # Validate PDF magic header
        if not file_bytes.startswith(b"%PDF-"):
            raise ValueError(f"File '{filename}' does not appear to be a valid PDF format.")

        try:
            stream = io.BytesIO(file_bytes)
            reader = pypdf.PdfReader(stream)
        except (PdfReadError, Exception) as exc:
            raise ValueError(f"Could not parse '{filename}' as a PDF: {exc}") from exc

        if reader.is_encrypted:
            try:
                # Attempt empty password decrypt
                decrypted = reader.decrypt("")
                if not decrypted:
                    raise ValueError("Password-protected or encrypted PDFs are not supported.")
            except Exception as exc:
                raise ValueError("Password-protected or encrypted PDFs are not supported.") from exc

        page_count = len(reader.pages)
        if page_count == 0:
            raise ValueError(f"PDF document '{filename}' contains no pages.")

        extracted_pages: List[ExtractedPage] = []
        total_text_parts: List[str] = []

        for idx, page in enumerate(reader.pages):
            try:
                page_text = page.extract_text() or ""
            except Exception as exc:
                page_text = ""
            
            clean_page_text = page_text.strip()
            extracted_pages.append(
                ExtractedPage(
                    page_number=idx + 1,
                    text=clean_page_text,
                    char_count=len(clean_page_text),
                )
            )
            if clean_page_text:
                total_text_parts.append(clean_page_text)

        full_text = "\n\n".join(total_text_parts).strip()

        # Check for scanned or image-only PDF
        if not full_text:
            raise ValueError(
                f"Scanned or image-only PDF detected in '{filename}'. "
                "No extractable text was found. Please upload a PDF containing digital text."
            )

        return PDFExtractionResult(
            text=full_text,
            page_count=page_count,
            char_count=len(full_text),
            pages=extracted_pages,
        )


pdf_extractor_service = PDFExtractorService()
