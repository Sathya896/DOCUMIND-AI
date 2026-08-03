"""Unit tests for upload validation logic (no FastAPI, no I/O)."""

import pytest

from app.utils.exceptions import InvalidFileError
from app.utils.file_validator import (
    validate_file_size,
    validate_filename,
    validate_pdf_signature,
)


def test_validate_filename_accepts_pdf():
    assert validate_filename("report.PDF") == "report.PDF"


def test_validate_filename_rejects_non_pdf():
    with pytest.raises(InvalidFileError):
        validate_filename("report.docx")


def test_validate_filename_rejects_missing_filename():
    with pytest.raises(InvalidFileError):
        validate_filename(None)


def test_validate_file_size_rejects_empty_file():
    with pytest.raises(InvalidFileError):
        validate_file_size(0)


def test_validate_file_size_rejects_oversized_file(monkeypatch: pytest.MonkeyPatch):
    from app.config.settings import settings

    monkeypatch.setattr(settings, "MAX_UPLOAD_SIZE_MB", 1)
    with pytest.raises(InvalidFileError):
        validate_file_size((2 * 1024 * 1024))


def test_validate_pdf_signature_accepts_real_pdf_bytes():
    validate_pdf_signature(b"%PDF-1.7\n...")  # should not raise


def test_validate_pdf_signature_rejects_non_pdf_bytes():
    with pytest.raises(InvalidFileError):
        validate_pdf_signature(b"not a pdf at all")
