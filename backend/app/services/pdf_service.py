"""
PDF ingestion: saving uploads to disk and extracting their text.

WHAT IS PyMuPDF (`fitz`)?
-----------------------------
PyMuPDF is a Python binding for MuPDF, a lightweight, very fast PDF/XPS
rendering library written in C. We use it purely for text extraction here.
Compared to alternatives:

* `PyPDF2` - pure Python, slower, and historically less accurate at
  preserving reading order for complex layouts (multi-column PDFs, tables).
* `pdfminer.six` - very accurate but noticeably slower on large files.
* `PyMuPDF` - written in C, extremely fast, and handles most real-world
  PDFs (including scanned-with-OCR-layer PDFs) well. Speed matters here
  because text extraction happens synchronously on every upload request.

WHY EXTRACT PAGE-BY-PAGE INSTEAD OF ONE BIG STRING?
--------------------------------------------------------
Keeping text separated by page lets us record *which page* a chunk came
from later (see `chunking_service.py`). This page number is what lets the
UI show "Source: report.pdf, page 4" - a small detail that makes the RAG
system feel trustworthy and verifiable rather than a black box.
"""

import uuid
from pathlib import Path

import fitz  # PyMuPDF

from app.config.settings import settings
from app.utils.exceptions import TextExtractionError
from app.utils.file_validator import (
    validate_file_size,
    validate_filename,
    validate_pdf_signature,
)
from app.utils.logger import get_logger

logger = get_logger(__name__)


def build_storage_path(original_filename: str) -> Path:
    """Generate a collision-free path to store an uploaded file at.

    WHY NOT JUST USE THE ORIGINAL FILENAME?
    Two users could both upload "report.pdf". Using the original name as the
    on-disk filename would let the second upload silently overwrite the
    first. Prefixing a UUID guarantees uniqueness while keeping the original
    name (for display purposes) safely stored in the database instead.
    """
    safe_suffix = Path(original_filename).suffix.lower()
    unique_name = f"{uuid.uuid4().hex}{safe_suffix}"
    return settings.UPLOAD_DIR / unique_name


def save_pdf_bytes(filename: str, file_bytes: bytes) -> Path:
    """Validate and persist raw PDF bytes to the uploads directory.

    Validation happens *before* any disk write, so an invalid upload never
    leaves a partial/garbage file behind.
    """
    validate_filename(filename)
    validate_file_size(len(file_bytes))
    validate_pdf_signature(file_bytes)

    destination = build_storage_path(filename)
    destination.write_bytes(file_bytes)
    logger.info("Saved uploaded file '%s' to '%s'", filename, destination)
    return destination


def extract_text_by_page(file_path: Path) -> list[str]:
    """Extract text from a PDF, returning one string per page.

    `fitz.open()` parses the PDF's structure; `page.get_text()` walks the
    page's content stream and returns the visible text in (roughly) reading
    order. We deliberately catch and wrap any parsing failure - a corrupted
    or password-protected PDF should surface as a clean, user-facing error
    rather than an unhandled crash.
    """
    try:
        with fitz.open(file_path) as pdf_document:
            if pdf_document.is_encrypted:
                raise TextExtractionError(
                    "This PDF is password-protected and cannot be processed."
                )

            pages_text = [page.get_text().strip() for page in pdf_document]
    except TextExtractionError:
        raise
    except Exception as exc:  # noqa: BLE001 - we intentionally wrap ALL fitz errors
        logger.exception("Failed to extract text from '%s'", file_path)
        raise TextExtractionError(
            f"Could not read '{file_path.name}'. The file may be corrupted."
        ) from exc

    non_empty_pages = [text for text in pages_text if text]
    if not non_empty_pages:
        raise TextExtractionError(
            "No extractable text was found in this PDF. "
            "It may be a scanned image without OCR text."
        )

    return pages_text
